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


class SummedExactPilotTests(unittest.TestCase):
    def query(self, grid=((H, 1, H),), mines=1, **kwargs):
        return q.ExactRequest(grid, mines, 2, kwargs.pop("allow_guess", True),
                              base_backend=q.UNIT10_SUMMED, **kwargs)

    def assert_charge(self, result):
        d = result.base_result.diagnostics
        self.assertTrue(result.work_accounting_complete)
        self.assertEqual((result.counter_units_total, result.counter_primary_work,
                          result.counter_auxiliary_work),
                         (d.units_total, d.primary_work, d.auxiliary_work))
        self.assertEqual(result.counter_units_total, result.counter_primary_work + result.counter_auxiliary_work)
        self.assertEqual((result.counter_backend_calls, result.backend_calls, result.exact_work), (1, 1, 0))
        self.assertEqual(result.counter_settlement.status, "SETTLED")

    def test_backend_selection_preserves_safe_minrisk_flag_and_blocked_semantics(self):
        cases = [(((1, F, 1), (H, H, H), (1, H, 1)), 1, False),
                 (((H, 1, H, F, F, F, F, F),), 2, True),
                 (((H, 1, H),), 1, False), (((H,),), 1, True)]
        for grid, mines, guess in cases:
            old = q.choose_exact(q.ExactRequest(grid, mines, 2, guess))
            new = q.choose_exact(self.query(grid, mines, allow_guess=guess))
            self.assertEqual((new.status, new.reason, new.sequence, new.mine_probability,
                              new.terminal_outcome),
                             (old.status, old.reason, old.sequence, old.mine_probability,
                              old.terminal_outcome))
            self.assertEqual((new.base_result.base.total_worlds, new.base_result.base.marginals),
                             (old.base_result.base.total_worlds, old.base_result.base.marginals))
            self.assertEqual(new.base_backend, q.UNIT10_SUMMED)
            self.assertNotEqual(new.request_id, old.request_id)
            self.assertNotEqual(new.pilot_id, old.pilot_id)
            self.assertEqual(old.counter_units_total, 0)
            self.assert_charge(new)
        with patch.object(q, "count_base", side_effect=AssertionError("fast proof must not count")):
            fast = q.choose_exact(self.query(((F, 0),), 0, allow_guess=False))
        self.assertEqual(fast.sequence, (EvidenceInput("FLAG", 0, 0), EvidenceInput("OPEN", 0, 0)))
        self.assertEqual((fast.basis, fast.counter_backend_calls, fast.counter_units_total), ("BASIC_RULES", 0, 0))

    def test_dto_size_precheck_identity_types_and_limits(self):
        self.assertEqual(fields(q.ExactRequest)[-1].name, "base_backend")
        self.assertEqual(fields(q.ExactLimits)[-1].name, "counter_units")
        grid480 = ((H,) * 30,) * 16
        self.assertEqual(len(self.query(grid480, 99).observation), 16)
        oversized = ((object(),) * 481,)
        with patch.object(q, "BeliefRequest", side_effect=AssertionError("converted before bound")):
            with self.assertRaisesRegex(ValueError, "CELL_LIMIT_BEFORE_ID"):
                self.query(oversized)
        payload = self.query().to_payload()
        payload["observation"] = oversized
        with patch.object(q, "_grid_payload", side_effect=AssertionError("decoded before bound")):
            with self.assertRaisesRegex(ValueError, "CELL_LIMIT_BEFORE_ID"):
                q.ExactRequest.from_payload(payload)
        legacy = q.choose_exact(q.ExactRequest(((H,) * 481,), 1, 2, True))
        self.assertEqual((legacy.status, legacy.reason), ("UNSUPPORTED", "CELL_LIMIT"))
        lower = q.choose_exact(self.query(limits=q.ExactLimits(max_cells=2)))
        self.assertEqual((lower.status, lower.reason), ("UNSUPPORTED", "CELL_LIMIT"))
        for invalid in (True, -1, 200001, 1.0):
            with self.assertRaises(ValueError):
                q.ExactLimits(counter_units=invalid)
        for backend in (None, True, "module.function", ""):
            with self.assertRaises(ValueError):
                replace(self.query(), base_backend=backend)
        ids = set()
        for backend in (q.UNIT4_LEGACY, q.UNIT10_SUMMED):
            for seconds in (2, 2.0):
                original = replace(self.query(), base_backend=backend,
                                   limits=q.ExactLimits(max_seconds=seconds))
                restored = q.ExactRequest.from_payload(json.loads(json.dumps(original.to_payload())))
                self.assertEqual(restored, original)
                self.assertIs(type(restored.limits.max_seconds), type(seconds))
                self.assertEqual(restored.identity, original.identity)
                ids.add(restored.identity)
        self.assertEqual(len(ids), 4)

    def test_zero_exact_and_counter_caps_and_exact_remaining_lease(self):
        zero = q.choose_exact(self.query(limits=q.ExactLimits(counter_units=0)))
        self.assertEqual((zero.status, zero.reason, zero.counter_backend_calls),
                         ("INSUFFICIENT", "ZERO_COUNTER_WORK_LIMIT", 0))
        self.assertIsNone(zero.local_result)
        fast_zero = q.choose_exact(self.query(((F, 0),), 0, limits=q.ExactLimits(counter_units=0)))
        self.assertEqual(fast_zero.reason, "ZERO_COUNTER_WORK_LIMIT")
        for cap in (114, 115):
            result = q.choose_exact(self.query(limits=q.ExactLimits(exact_work=0, counter_units=cap)))
            self.assertEqual(result.status, "READY" if cap == 115 else "INSUFFICIENT")
            self.assert_charge(result)
            self.assertEqual(result.counter_settlement.lease_units, cap)
            self.assertLessEqual(result.counter_units_total, cap)
        legacy = q.choose_exact(q.ExactRequest(((H, 1, H),), 1, 2, True,
                                              limits=q.ExactLimits(counter_units=0)))
        self.assertEqual(legacy.status, "READY")
        self.assertEqual(legacy.counter_units_total, 0)

    def test_every_counter_status_settles_positive_spend_before_status(self):
        from stage4_belief import BaseResult
        real = q.count_base
        for status in ("COMPLETE", "INSUFFICIENT", "CANCELLED", "ERROR", "INCONSISTENT_INPUT", "UNSUPPORTED"):
            def changed(query, **kwargs):
                raw = real(query, **kwargs)
                return raw if status == "COMPLETE" else replace(raw, status=status, reason="REGISTERED_STOP",
                    base=BaseResult(status, "REGISTERED_STOP", 0 if status == "INCONSISTENT_INPUT" else None))
            with patch.object(q, "count_base", changed):
                result = q.choose_exact(self.query())
            self.assert_charge(result)
            self.assertGreater(result.counter_units_total, 0)
            if status != "COMPLETE":
                self.assertEqual(result.status, status)
                self.assertFalse(result.sequence)
                self.assertIsNone(result.mine_probability)

    def test_parent_cancel_callback_error_and_time_settle_before_stop(self):
        real = q.count_base
        for kind, status in (("cancel", "CANCELLED"), ("callback", "ERROR"), ("time", "INSUFFICIENT")):
            returned = [False]
            def counted(query, **kwargs):
                result = real(query, **kwargs)
                returned[0] = True
                return result
            def callback():
                return (1 if kind == "callback" else kind == "cancel") if returned[0] else False
            with patch.object(q, "count_base", counted), patch.object(q, "perf_counter",
                    lambda: 3.0 if kind == "time" and returned[0] else 0.0):
                result = q.choose_exact(self.query(), cancelled=callback)
            self.assertEqual(result.status, status)
            self.assert_charge(result)
            self.assertEqual(result.base_result.status, "COMPLETE")
            self.assertFalse(result.sequence)
            self.assertIsNone(result.mine_probability)

    def test_during_count_and_final_publish_cancel_preserve_atomic_spend(self):
        import stage4_belief_counter as counter
        original = counter._Budget.check
        for stage in ("prepare", "publish.final"):
            pending = [False]
            def checkpoint(budget):
                if budget.stage == stage and budget.total > 0:
                    pending[0] = True
                return original(budget)
            with patch.object(counter._Budget, "check", checkpoint):
                result = q.choose_exact(self.query(), cancelled=lambda: pending[0])
            self.assertEqual(result.status, "CANCELLED")
            self.assert_charge(result)
            self.assertGreater(result.counter_units_total, 0)
            self.assertIsNone(result.base_result.base.total_worlds)
            self.assertFalse(result.base_result.base.marginals)
            self.assertFalse(result.sequence)

    def test_invalid_counter_usage_is_unknown_and_valid_spend_survives_bad_binding(self):
        real = q.count_base
        variants = [lambda raw: {},
                    lambda raw: replace(raw, diagnostics=replace(raw.diagnostics, units_total=True)),
                    lambda raw: replace(raw, diagnostics=replace(raw.diagnostics, preparation_visits=-1)),
                    lambda raw: replace(raw, diagnostics=replace(raw.diagnostics, units_total=1)),
                    lambda raw: replace(raw, diagnostics=replace(raw.diagnostics,
                        preparation_visits=200001, auxiliary_work=200001, primary_work=0,
                        units_total=200001, forced_assignments=0, branch_attempts=0, dp_products=0,
                        constraint_visits=0, constraint_cell_visits=0, memo_operations=0,
                        histogram_updates=0, publish_visits=0))]
        for mutate in variants:
            with patch.object(q, "count_base", lambda query, **kw: mutate(real(query, **kw))):
                result = q.choose_exact(self.query())
            self.assertEqual(result.status, "ERROR")
            self.assertFalse(result.work_accounting_complete)
            self.assertEqual(result.counter_settlement.status, "UNKNOWN_SPEND")
            self.assertIsNone(result.counter_settlement.units_total)
            self.assertFalse(result.sequence)
        for name in ("request_id", "problem_id", "backend_version", "work_accounting_version"):
            with patch.object(q, "count_base", lambda query, **kw: replace(real(query, **kw), **{name: "wrong"})):
                result = q.choose_exact(self.query())
            self.assertEqual(result.status, "ERROR")
            self.assert_charge(result)
            self.assertFalse(result.sequence)
        with patch.object(q, "count_base", side_effect=RuntimeError("no response")):
            result = q.choose_exact(self.query())
        self.assertEqual(result.status, "ERROR")
        self.assertFalse(result.work_accounting_complete)
        self.assertEqual(result.counter_settlement.status, "UNKNOWN_SPEND")
        self.assertEqual(result.counter_backend_calls, 1)

    def test_invalid_complete_base_is_charged_but_never_cached(self):
        real = q.count_base
        def corrupt(query, **kwargs):
            raw = real(query, **kwargs)
            bad = replace(raw.base.marginals[0], probability=Fraction(0))
            return replace(raw, base=replace(raw.base, marginals=(bad,) + raw.base.marginals[1:]))
        pilot = q.ExactPilot()
        with patch.object(q, "count_base", corrupt):
            result = pilot.choose(self.query())
        self.assertEqual(result.status, "ERROR")
        self.assert_charge(result)
        self.assertEqual(result.cache_entries, 0)

    def test_cache_backend_flag_origin_capacity_and_incomplete_isolation(self):
        pilot = q.ExactPilot(cache_entries=2)
        query = self.query()
        first = pilot.choose(query)
        legacy = pilot.choose(replace(query, base_backend=q.UNIT4_LEGACY))
        hit = pilot.choose(replace(query, counted_inputs=99, limits=q.ExactLimits(counter_units=1)))
        self.assertFalse(legacy.cache_hit)
        self.assertTrue(hit.cache_hit)
        self.assertEqual((hit.counter_units_total, hit.counter_backend_calls, hit.backend_calls), (0, 0, 0))
        self.assertEqual((hit.base_result, hit.base_request, hit.base_origin_request_id),
                         (first.base_result, first.base_request, first.base_origin_request_id))
        self.assertGreater(hit.local_work, 0)
        self.assertEqual(pilot.choose(replace(query, limits=q.ExactLimits(counter_units=0))).reason,
                         "ZERO_COUNTER_WORK_LIMIT")
        changed = pilot.choose(replace(query, observation=((F, 1, H),)))
        self.assertFalse(changed.cache_hit)
        self.assertEqual(changed.cache_entries, 2)
        self.assertFalse(pilot.choose(query).cache_hit)
        pilot.clear()
        low = pilot.choose(replace(query, limits=q.ExactLimits(counter_units=114)))
        self.assertEqual(low.cache_entries, 0)
        self.assertFalse(pilot.choose(query).cache_hit)
        with self.assertRaises(ValueError):
            q.ExactPilot(cache_entries=257)

    def test_bounded_internal_stack_error_is_atomic_charged_and_not_cached(self):
        import stage4_belief_counter as counter
        pilot = q.ExactPilot()
        with patch.object(counter, "_weighted", side_effect=RecursionError("bounded injection, not deep recursion")):
            result = pilot.choose(self.query())
        self.assertEqual((result.status, result.reason), ("ERROR", "BASE_INTERNAL_ERROR"))
        self.assert_charge(result)
        self.assertGreater(result.counter_units_total, 0)
        self.assertIsNone(result.base_result.base.total_worlds)
        self.assertFalse(result.base_result.base.marginals)
        self.assertFalse(result.sequence)
        self.assertEqual(result.cache_entries, 0)

    def test_new_public_boundary_and_recursive_guards_reset(self):
        import stage4_objective_pilot as g
        query = self.query()
        for name in ("actual_layout", "active", "wasted", "progress_bbbv", "mode", "target"):
            payload = query.to_payload()
            payload[name] = 1
            with self.assertRaises(ValueError):
                q.ExactRequest.from_payload(payload)
        with self.assertRaises(ValueError):
            replace(query, counted_inputs=True)
        real, nested = q.count_base, []
        def probe(child, **kwargs):
            nested.append(q.choose_exact(query))
            nested.append(g.choose_objective(g.ObjectiveRequest(query.observation, 1, 2, "M", True,
                                                               base_backend=q.UNIT10_SUMMED)))
            return real(child, **kwargs)
        with patch.object(q, "count_base", probe):
            outer = q.choose_exact(query)
        self.assertEqual(outer.status, "READY")
        self.assertEqual([r.reason for r in nested], ["RECURSIVE_Q_FORBIDDEN", "RECURSIVE_G_FORBIDDEN"])
        self.assertFalse(q._Q_ACTIVE.get())
        self.assertFalse(g._G_ACTIVE.get())
        self.assertEqual(q.choose_exact(query).status, "READY")


if __name__ == "__main__":
    unittest.main()

