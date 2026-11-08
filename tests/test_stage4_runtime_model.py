"""Small exhaustive posterior witnesses, independent transitions and budgets."""
from dataclasses import fields, replace
from fractions import Fraction
import unittest
from unittest.mock import patch

import stage4_runtime_model as m
from stage4_policy import ModelScore, model_order, _shortlist
from tests import stage4_pilot_oracle as oracle

AUDIT = None
H, F = -2, -3
WITNESSES = {"G009": (((0, 1, F, H), (0, 1, H, 1)), 3),
             "G001": (((H, 1, H), (H, H, F)), 2),
             "G010": (((H, 1, H), (H, H, H)), 1)}
TINY = m.ModelLimits(samples=64, shortlist=6, rows=384, diagnostic=True)


def query(name="G001", mode="M", **kwargs):
    grid, count = WITNESSES[name]
    return m.ModelRequest(grid, 1, count, mode, True, Fraction(6, 5) if mode == "R" else None,
                          "units24-26-independent-planning-v1", limits=TINY, **kwargs)


class RuntimeModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = {}
        for name in WITNESSES:
            for mode in ("S", "M", "R"):
                q = query(name, mode)
                result = m.evaluate_model(q)
                cls.results[name, mode] = result
                if AUDIT:
                    AUDIT.emit("tiny_witness", dict(name=name, mode=mode, request=q, result=result,
                        classification="registered_small_exhaustive_diagnostic_not_default_probe"))

    def test_common_exhaustive_bank_and_exact_eligibility(self):
        for name, (grid, _) in WITNESSES.items():
            independent = oracle.posterior(grid, 1)
            bank = None
            for mode in ("S", "M", "R"):
                result = self.results[name, mode]
                self.assertEqual(result.status, "COMPLETE", (name, mode, result.reason, result.error))
                self.assertEqual(result.model_id, "RUNTIME_COMMON_POSTERIOR_THEN_PUBLIC_F_V2_FIXED_LIMITS")
                for call in result.calls:
                    self.assertEqual(call.request.limits, m.FollowupLimits())
                self.assertEqual({frozenset(s.mines) for s in result.posterior.samples},
                                 {frozenset(s) for s in independent["layouts"]})
                if bank is not None:
                    self.assertEqual(bank, result.posterior.samples)
                bank = result.posterior.samples
                selected = {s.candidate_id for s in result.shortlist if s.included}
                counts = dict(independent["M"])
                for c in result.root.candidates:
                    survival = Fraction(sum(not set(c.targets) & set(w) for w in independent["layouts"]), independent["D"])
                    self.assertEqual(c.survival_probability, survival)
                    if mode == "S" and c.candidate_id in selected:
                        if any(v == 0 for v in counts.values()):
                            self.assertEqual(survival, 1)
                        else:
                            self.assertEqual(c.kind, "OPEN")
                            self.assertEqual(counts[c.pivot], min(counts.values()))

    def test_rows_scores_and_selection_independent_atomic_replay(self):
        for (name, mode), result in self.results.items():
            grid, prefix = WITNESSES[name]
            self.assertEqual(result.status, "COMPLETE", result.error)
            for row in result.rows:
                sample = result.posterior.samples[row.sample_index]
                replay = oracle.replay(grid, 1, sample.mines,
                    [(a.action, a.x, a.y) for a in row.actions], prefix)
                self.assertEqual((replay["outcome"], replay["X"], replay["added_inputs"]),
                                 (row.outcome, row.value_x, row.added_inputs))
                # Rebuild the prefix before each F call independently. F gets
                # only public state, never the independent world's layout.
                candidate = next(c for c in result.root.candidates if c.candidate_id == row.candidate_id)
                world = oracle.World(grid, 1, sample.mines)
                offset = 0
                for a in candidate.sequence:
                    world.step((a.action, a.x, a.y)); offset += 1
                    if world.outcome:
                        break
                for i in row.f_call_indices:
                    call = result.calls[i]
                    self.assertEqual(call.request.observation, world.observation)
                    self.assertEqual(call.request.counted_inputs, prefix+offset)
                    public = oracle.posterior(world.observation, 1)
                    marginal = dict(public["M"])
                    if call.result.status == "READY":
                        last = call.result.sequence[-1]
                        if last.action == "OPEN":
                            risk = marginal[last.x, last.y]
                            self.assertEqual(risk, 0 if any(v == 0 for v in marginal.values()) else min(marginal.values()))
                        for a in call.result.sequence:
                            world.step((a.action, a.x, a.y)); offset += 1
                            if world.outcome:
                                break
                self.assertEqual(offset, row.added_inputs)
            for score in result.scores:
                rows = [r for r in result.rows if r.candidate_id == score.candidate_id]
                self.assertEqual(score.rollout_mean_x, sum((r.value_x for r in rows), Fraction())/len(rows))
                self.assertEqual(score.rollout_win_rate, Fraction(sum(r.outcome == "WON" for r in rows), len(rows)))
                if mode == "R":
                    self.assertEqual(score.rollout_hit_rate, Fraction(sum(r.outcome == "WON" and r.value_x >= Fraction(6, 5) for r in rows), len(rows)))
            eligible, chosen, _ = _shortlist(result.root, query(name, mode))
            order = {c.candidate_id:i for i, c in enumerate(eligible)}
            candidates = {c.candidate_id:c for c in chosen}
            def independent_key(s):
                common = (s.rollout_mean_x, s.rollout_win_rate, candidates[s.candidate_id].survival_probability, -order[s.candidate_id])
                return (s.rollout_hit_rate,)+common if mode == "R" else common
            self.assertEqual(result.selected_candidate_id, max(result.scores, key=independent_key).candidate_id)

    def test_cache_on_off_same_bank_actions_terminals_and_costs(self):
        observed_hits = 0
        for name in WITNESSES:
            on = self.results[name, "M"]
            q = replace(query(name), limits=replace(TINY, cache_entries=0))
            off = m.evaluate_model(q)
            self.assertEqual(off.status, "COMPLETE", off.error)
            for call in off.calls:
                self.assertEqual(call.request.limits, m.FollowupLimits())
            self.assertEqual((on.sequence, on.scores, on.posterior.samples), (off.sequence, off.scores, off.posterior.samples))
            self.assertEqual(on.rows, off.rows)
            self.assertEqual(off.usage.f_hits, 0)
            self.assertEqual(on.usage.f_lookups, on.usage.f_hits+on.usage.f_misses)
            self.assertLessEqual(on.usage.q_calls, off.usage.q_calls)
            self.assertLessEqual(on.usage.kernel_calls, off.usage.kernel_calls)
            observed_hits += on.usage.f_hits
            for call in on.calls:
                self.assertEqual(call.origin_request_id, call.result.request_id)
                self.assertEqual(call.request.logical_key, call.result.request.logical_key)
            if AUDIT:
                AUDIT.emit("cache_equivalence", dict(name=name, on_usage=on.usage, off_request=q, off_result=off, equal=True))
        self.assertGreater(observed_hits, 0)

    def test_synthetic_objective_difference_separate_from_witness(self):
        a = ModelScore("mean", Fraction(1, 2), Fraction(1, 2), Fraction(0), 10, 10, m.F_ID)
        b = ModelScore("target", Fraction(2, 5), Fraction(2, 5), Fraction(1, 5), 10, 10, m.F_ID)
        self.assertGreater(model_order(a, Fraction(1), 0, "M"), model_order(b, Fraction(1), 1, "M"))
        self.assertLess(model_order(a, Fraction(1), 0, "R"), model_order(b, Fraction(1), 1, "R"))

    def test_partial_matrix_zero_limits_and_cancel_are_atomic(self):
        for limits in (replace(TINY, row_inputs=0), replace(TINY, virtual_inputs=0),
                       replace(TINY, f_lookups=0), replace(TINY, f_misses=0),
                       replace(TINY, sampler_work=0), replace(TINY, rows=0), replace(TINY, max_seconds=0)):
            result = m.evaluate_model(replace(query(), limits=limits))
            self.assertEqual(result.status, "RESOURCE_LIMIT", (result.status, result.reason, result.error))
            self.assertFalse(result.sequence)
            self.assertFalse(result.scores)
            self.assertEqual(result.information, "INCOMPLETE_NO_INFORMATION")
        self.assertEqual(m.evaluate_model(query(), cancelled=lambda: True).status, "CANCELLED")
        self.assertEqual(m.evaluate_model(query(), cancelled=lambda: 1).status, "ERROR")

    def test_guess_blocked_complete_zero_differs_from_no_information(self):
        result = m.evaluate_model(replace(query("G009", "S"), allow_guess=False))
        self.assertEqual(result.status, "COMPLETE", result.error)
        self.assertTrue(all(r.outcome == "GUESS_BLOCKED" and r.value_x == 0 for r in result.rows))
        self.assertEqual(result.information, "COMPLETE_ALL_ZERO")
        high = m.evaluate_model(replace(query("G010", "R"), target=Fraction(100)))
        self.assertEqual(high.target_status, "NO_HIT_EVIDENCE_MEAN_X_TIEBREAK")
        self.assertEqual(m.evaluate_model(replace(query("G010", "R"), target=None)).status, "TARGET_REQUIRED")

    def test_f_public_boundary_versions_and_no_recursion(self):
        self.assertEqual({f.name for f in fields(m.FollowupRequest)},
            {"observation", "num_mines", "counted_inputs", "allow_guess", "prior_id", "limits"})
        q = m.FollowupRequest(((0, H),), 0, 1, False)
        for kind, fid in (("indexed", m.F_ID), ("v1", m.V1_F_ID)):
            result = m.choose_followup(replace(q, limits=replace(q.limits, kernel_kind=kind)))
            self.assertEqual(result.status, "READY", result.error)
            self.assertEqual(result.followup_id, fid)
            self.assertEqual(result.source, "PUBLIC_KERNEL")
        token = m._F_ACTIVE.set(True)
        try:
            self.assertEqual(m.evaluate_model(query()).status, "ERROR")
            self.assertEqual(m.choose_followup(q).status, "ERROR")
        finally:
            m._F_ACTIVE.reset(token)

    def test_unknown_spend_settles_all_reserved_f_resources(self):
        with patch.object(m, "choose_followup", side_effect=RuntimeError("simulated backend failure")):
            result = m.evaluate_model(query())
        self.assertEqual(result.status, "ERROR")
        self.assertFalse(result.usage.accounting_complete)
        self.assertFalse(result.sequence)
        unknown = [s.resource for s in result.settlements if s.status == "UNKNOWN_SPEND"]
        self.assertEqual(unknown, ["kernel_work", "q_local", "unit10_units"])

    def test_request_roundtrip_and_diagnostic_boundary(self):
        q = replace(query(), planning_seed=2**70+3)
        self.assertEqual(m.ModelRequest.from_payload(q.to_payload()), q)
        with self.assertRaises(ValueError):
            m.ModelLimits(samples=64)
        with self.assertRaises(ValueError):
            m.ModelRequest((tuple([H]*17),), 1, 1, limits=TINY)
        result = m.evaluate_model(m.ModelRequest((tuple([H]*8),), 3, 1, "M", True,
            limits=replace(TINY, samples=8)))
        self.assertEqual(result.status, "UNSUPPORTED")


class FixedFollowupLimitsTests(unittest.TestCase):
    """F1 reservation boundaries; fake F cases are labelled independently."""
    CAPS = (("kernel_work", 500_000, "KERNEL_BUDGET"),
            ("q_local", 20_000, "Q_LOCAL_BUDGET"),
            ("unit10_units", 200_000, "UNIT10_BUDGET"))

    def emit(self, case, **value):
        if AUDIT:
            AUDIT.emit("f1_cases", dict(case=case, **value))

    def fake(self, request, *, cancelled=None):
        self.assertIsNotNone(cancelled)
        self.assertFalse(cancelled())
        usage = m.RuntimeUsage(kernel_calls=1, kernel_work=7, q_calls=1,
                               q_local=11, unit10_calls=1, unit10_units=13)
        result = m.FollowupResult(request.limits.followup_id, request.identity, request,
            "GUESS_BLOCKED", "INJECTED_COMPLETE", (), "EXACT_Q", "GUESS_BLOCKED",
            None, None, None, None, None, usage,
            tuple(m.Settlement(name, cap, getattr(usage, name), "SETTLED")
                  for name, cap, _ in self.CAPS), True, 0.0)
        if AUDIT:
            AUDIT.emit("f1_injected_f", dict(request=request, result=result))
        return result

    def followup(self, **kwargs):
        return m.FollowupRequest(((0, H),), 0, 1, False, **kwargs)

    def assert_stop(self, reason, fn):
        with self.assertRaises(m._Stop) as raised:
            fn()
        self.assertEqual((raised.exception.status, raised.exception.reason),
                         ("RESOURCE_LIMIT", reason))

    def test_three_work_resources_cap_minus_exact_plus(self):
        with patch.object(m, "perf_counter", return_value=100.0):
            for resource, cap, reason in self.CAPS:
                for delta in (-1, 0, 1):
                    with self.subTest(resource=resource, remaining=cap+delta):
                        q = replace(query(), limits=replace(TINY, **{resource: cap+100}))
                        budget = m._Budget(q, None)
                        budget.usage = replace(budget.usage, **{resource: 100-delta})
                        before = budget.usage
                        cache, calls, fq = m._FollowupCache(1), [], self.followup()
                        with patch.object(m, "choose_followup", side_effect=self.fake) as backend:
                            if delta < 0:
                                self.assert_stop(reason, lambda: cache.choose(fq, budget, calls))
                                backend.assert_not_called()
                                self.assertEqual((budget.usage.f_misses, calls, budget.settlements), (0, [], []))
                            else:
                                result = cache.choose(fq, budget, calls)
                                self.assertEqual(backend.call_count, 1)
                                self.assertEqual(backend.call_args.args[0].limits, m.FollowupLimits())
                                for field, reserved, _ in self.CAPS:
                                    self.assertEqual(getattr(budget.usage, field),
                                        getattr(before, field)+getattr(result.usage, field))
                                    self.assertIn(m.Settlement(field, reserved, getattr(result.usage, field), "SETTLED"),
                                                  budget.settlements)
                        self.emit("work_boundary", resource=resource, remaining=cap+delta,
                            backend_calls=backend.call_count, usage=budget.usage, settlements=budget.settlements)

    def test_five_second_reservation_controlled_clock(self):
        with patch.object(m, "perf_counter", return_value=100.0):
            for seconds in (4.999, 5.0, 5.001):
                with self.subTest(seconds=seconds):
                    budget = m._Budget(query(), None)
                    budget.deadline = 100.0+seconds
                    cache, calls = m._FollowupCache(1), []
                    with patch.object(m, "choose_followup", side_effect=self.fake) as backend:
                        if seconds < 5.0:
                            self.assert_stop("F_TIME_RESERVATION", lambda: cache.choose(self.followup(), budget, calls))
                            backend.assert_not_called()
                            self.assertFalse(budget.settlements)
                        else:
                            cache.choose(self.followup(), budget, calls)
                            self.assertEqual(backend.call_count, 1)
                            self.assertEqual(backend.call_args.args[0].limits.max_seconds, 5.0)
                    self.emit("time_boundary", remaining=seconds, backend_calls=backend.call_count,
                              settlements=budget.settlements, clock="controlled_no_sleep")

    def test_complete_cache_hit_needs_no_new_work_or_time_reservation(self):
        with patch.object(m, "perf_counter", return_value=100.0):
            budget = m._Budget(query(), None)
            cache, calls, fq = m._FollowupCache(1), [], self.followup()
            with patch.object(m, "choose_followup", side_effect=self.fake) as backend:
                original = cache.choose(fq, budget, calls)
                budget.usage = replace(budget.usage, **{name:getattr(TINY, name) for name, _, _ in self.CAPS})
                budget.deadline = 100.001
                before, settlements = budget.usage, tuple(budget.settlements)
                self.assertIs(cache.choose(fq, budget, calls), original)
                self.assertEqual(backend.call_count, 1)
                self.assertTrue(calls[-1].cache_hit)
                self.assertEqual(calls[-1].origin_request_id, original.request_id)
                for resource, _, _ in self.CAPS:
                    self.assertEqual(getattr(budget.usage, resource), getattr(before, resource))
                self.assertEqual(tuple(budget.settlements), settlements)
                different = replace(fq, counted_inputs=2)
                self.assert_stop("KERNEL_BUDGET", lambda: cache.choose(different, budget, calls))
                self.assertEqual(backend.call_count, 1)
                budget.usage = replace(budget.usage, kernel_work=0, q_local=0, unit10_units=0)
                self.assert_stop("F_TIME_RESERVATION", lambda: cache.choose(different, budget, calls))
                self.assertEqual(backend.call_count, 1)
            self.emit("cache_hit_vs_miss", calls=calls, usage=budget.usage, settlements=budget.settlements)

    def test_cache_rejects_bad_origin_key_status_and_accounting(self):
        with patch.object(m, "perf_counter", return_value=100.0):
            fq = self.followup()
            original = self.fake(fq, cancelled=lambda:False)
            different = replace(fq, counted_inputs=2)
            variants = {
                "request_id": replace(original, request_id="wrong"),
                "logical_key": replace(original, request=different, request_id=different.identity),
                "followup_id": replace(original, followup_id="wrong"),
                "incomplete": replace(original, status="RESOURCE_LIMIT"),
                "uncacheable": replace(original, cacheable=False),
                "error": replace(original, error="backend error"),
                "unknown_usage": replace(original, usage=replace(original.usage, accounting_complete=False)),
                "unknown_settlement": replace(original, settlements=(m.Settlement("kernel_work", 500000, None, "UNKNOWN_SPEND"),)),
                "wrong_total": replace(original, usage=replace(original.usage, kernel_work=8)),
            }
            for name, result in variants.items():
                with self.subTest(name=name):
                    budget, cache, calls = m._Budget(query(), None), m._FollowupCache(1), []
                    cache.entries[fq.logical_key] = result
                    with patch.object(m, "choose_followup") as backend, self.assertRaises(ValueError):
                        cache.choose(fq, budget, calls)
                    backend.assert_not_called()
                    self.assertFalse(calls)
                    self.emit("cache_rejection", kind=name, backend_calls=backend.call_count)

    def test_current_cancel_error_and_deadline_precede_cache_or_resource_gate(self):
        with patch.object(m, "perf_counter", return_value=100.0):
            fq = self.followup()
            original = self.fake(fq, cancelled=lambda:False)
            for hit in (False, True):
                for kind in ("cancel", "bad_callback", "callback_error", "deadline"):
                    with self.subTest(hit=hit, kind=kind):
                        def cancel():
                            if kind == "callback_error":
                                raise RuntimeError("injected external error")
                            return 1 if kind == "bad_callback" else kind == "cancel"
                        budget = m._Budget(replace(query(), limits=replace(TINY, kernel_work=0)), cancel)
                        if kind == "deadline":
                            budget.deadline = 100.0
                        cache, calls = m._FollowupCache(1), []
                        if hit:
                            cache.entries[fq.logical_key] = original
                        with patch.object(m, "choose_followup") as backend:
                            expected = TypeError if kind == "bad_callback" else RuntimeError if kind == "callback_error" else m._Stop
                            with self.assertRaises(expected) as raised:
                                cache.choose(fq, budget, calls)
                            if kind in ("cancel", "deadline"):
                                self.assertEqual(raised.exception.reason, "CANCELLED" if kind == "cancel" else "TIME_LIMIT")
                            backend.assert_not_called()
                        self.emit("current_constraint", cache_hit=hit, kind=kind, backend_calls=0)

    def test_miss_cancel_and_error_keep_unknown_reservations(self):
        with patch.object(m, "perf_counter", return_value=100.0):
            for kind in ("exception", "cancel_unknown", "cancel_known", "error_known"):
                with self.subTest(kind=kind):
                    fq, budget, cache, calls = self.followup(), m._Budget(query(), None), m._FollowupCache(1), []
                    def backend(request, **kwargs):
                        if kind == "exception":
                            raise RuntimeError("injected exception after reservation")
                        value = self.fake(request, **kwargs)
                        return replace(value, status="ERROR" if kind == "error_known" else "CANCELLED",
                            cacheable=False, usage=replace(value.usage, accounting_complete=kind != "cancel_unknown"))
                    with patch.object(m, "choose_followup", side_effect=backend):
                        if kind in ("exception", "cancel_unknown"):
                            with self.assertRaisesRegex(ValueError, "UNKNOWN_MODEL_BACKEND_SPEND"):
                                cache.choose(fq, budget, calls)
                            self.assertFalse(budget.usage.accounting_complete)
                            for resource, cap, _ in self.CAPS:
                                self.assertEqual(getattr(budget.usage, resource), cap)
                                self.assertIn(m.Settlement(resource, cap, None, "UNKNOWN_SPEND"), budget.settlements)
                        else:
                            result = cache.choose(fq, budget, calls)
                            self.assertEqual(result.status, "ERROR" if kind == "error_known" else "CANCELLED")
                            self.assertTrue(budget.usage.accounting_complete)
                        self.assertFalse(cache.entries)
                    self.emit("miss_failure_accounting", kind=kind, usage=budget.usage, settlements=budget.settlements)

    def test_model_gates_are_atomic_and_registered_kernel_kind_is_kept(self):
        with patch.object(m, "perf_counter", return_value=100.0):
            cases = [(resource, replace(TINY, **{resource:cap-1}), reason) for resource, cap, reason in self.CAPS]
            cases.append(("time", replace(TINY, max_seconds=4.999), "F_TIME_RESERVATION"))
            for name, limits, reason in cases:
                with self.subTest(gate=name), patch.object(m, "choose_followup") as backend:
                    result = m.evaluate_model(replace(query(), limits=limits))
                    self.assertEqual((result.status, result.reason), ("RESOURCE_LIMIT", reason))
                    self.assertEqual((result.sequence, result.selected_candidate_id, result.scores), ((), None, ()))
                    self.assertEqual(result.information, "INCOMPLETE_NO_INFORMATION")
                    self.assertTrue(result.usage.accounting_complete)
                    self.assertTrue(any(row.outcome == "UNRESOLVED" for row in result.rows))
                    for row in result.rows:
                        if row.outcome in ("UNRESOLVED", "NOT_STARTED"):
                            self.assertEqual((row.value_x, row.hit, row.virtual_b), (None, None, None))
                        self.assertTrue(all(i < len(result.calls) for i in row.f_call_indices))
                    backend.assert_not_called()
                    self.emit("model_gate", kind=name, result=result, backend_calls=0)
            with patch.object(m, "choose_followup", side_effect=self.fake) as backend:
                result = m.evaluate_model(replace(query(), limits=replace(TINY, kernel_kind="v1")))
            self.assertEqual(result.status, "COMPLETE", result.error)
            self.assertGreater(backend.call_count, 0)
            self.assertTrue(all(c.request.limits == m.FollowupLimits(kernel_kind="v1") for c in result.calls))
            self.assertEqual(result.followup_id, m.V1_F_ID)
            self.emit("kernel_kind", result=result, classification="injected_F_not_real_model_quality")

    def test_exhaustion_keeps_finished_rows_without_publishing_scores(self):
        original_row, finished = m._row, []
        def exhaust_after_first(*args):
            row, stopped = original_row(*args)
            if not finished:
                self.assertIsNone(stopped)
                self.assertIsNotNone(row.value_x)
                finished.append(row)
                budget = args[4]
                budget.usage = replace(budget.usage, kernel_work=budget.request.limits.kernel_work)
            return row, stopped
        with patch.object(m, "perf_counter", return_value=100.0), patch.object(m, "_row", side_effect=exhaust_after_first):
            result = m.evaluate_model(replace(query(), limits=replace(TINY, cache_entries=0)))
        self.assertEqual((result.status, result.reason), ("RESOURCE_LIMIT", "KERNEL_BUDGET"))
        self.assertEqual(result.rows[0], finished[0])
        self.assertEqual((result.sequence, result.selected_candidate_id, result.scores), ((), None, ()))
        self.assertTrue(any(r.outcome == "UNRESOLVED" and r.value_x is None for r in result.rows))
        self.emit("partial_matrix", result=result, classification="injected_remaining_budget_real_small_backend")

    def test_runtime_resource_gate_uses_existing_fallback_once(self):
        import stage4_runtime_policy as p
        grid, prefix = WITNESSES["G001"]
        request = p.RuntimeRequest(grid, 1, prefix, "M", True,
            limits=p.RuntimeLimits(model=m.ModelLimits(kernel_work=499999)))
        policy = p.RuntimePolicy()
        try:
            result = policy.choose(request)
        finally:
            policy.close()
        self.assertEqual((result.status, result.decision_source, result.model_status),
                         ("HEURISTIC_FALLBACK", "F", "RESOURCE_LIMIT"))
        self.assertEqual(result.model.reason, "KERNEL_BUDGET")
        self.assertEqual((result.model.sequence, result.model.selected_candidate_id, result.model.scores), ((), None, ()))
        self.assertEqual(result.model.usage.f_misses, 0)
        self.assertTrue(result.sequence)
        self.assertTrue(result.usage.accounting_complete)
        self.emit("runtime_fallback", request=request, result=result,
                  classification="real_small_model_and_real_F_no_engine_or_policy_owner")


if __name__ == "__main__":
    unittest.main()
