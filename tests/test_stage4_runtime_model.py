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


def assert_reuse_binding(test, call):
    """A lookup record keeps the identity of the request its result was computed for.

    That request may differ from the current one in counted_inputs only, and only
    for a cache hit; a miss is bound to the current request completely.
    """
    test.assertEqual(call.origin_request_id, call.result.request_id)
    test.assertEqual(call.result.request_id, call.result.request.identity)
    test.assertEqual(call.request.reuse_key, call.result.request.reuse_key)
    test.assertEqual(replace(call.result.request, counted_inputs=call.request.counted_inputs).logical_key,
                     call.request.logical_key)
    if not call.cache_hit:
        test.assertEqual(call.request.logical_key, call.result.request.logical_key)
        test.assertEqual(call.result.request_id, call.request.identity)


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
                self.assertEqual(result.model_id, "RUNTIME_COMMON_POSTERIOR_THEN_PUBLIC_F_V5_ROOT_BASE_REUSE")
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
                # S4_F_OBS_MEMO1: a hit may come from the same public state at another
                # counted-input total; everything else of the logical key still agrees.
                assert_reuse_binding(self, call)
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
                # A miss needs another public state: counted_inputs alone is a reuse
                # since S4_F_OBS_MEMO1 (ObservationReuseTests covers that hit).
                different = m.FollowupRequest(((H, 0),), 0, 1, False)
                self.assertNotEqual(different.reuse_key, fq.reuse_key)
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
            # Results that are consistent with their own request but belong to another
            # public state, guess setting or F cap must not answer this lookup.
            different = m.FollowupRequest(((H, 0),), 0, 1, False)
            guessing = replace(fq, allow_guess=True)
            capped = replace(fq, limits=replace(fq.limits, plan=m.PlanLimits(max_subsets=1)))
            variants = {
                "request_id": replace(original, request_id="wrong"),
                "logical_key": replace(original, request=different, request_id=different.identity),
                "guess_setting": replace(original, request=guessing, request_id=guessing.identity),
                "plan_cap": replace(original, request=capped, request_id=capped.identity),
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
                    cache.entries[fq.reuse_key] = result
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
                            cache.entries[fq.reuse_key] = original
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


class IndexedK100KTests(unittest.TestCase):
    """A separate fixed F, with legacy payloads and atomic gates preserved."""

    def limits(self, **changes):
        return replace(TINY, kernel_kind="indexed_k100k", **changes)

    def followup(self):
        return m.FollowupRequest(((0, H),), 0, 1, False,
            limits=m.fixed_followup_limits("indexed_k100k"))

    def fake(self, request, *, cancelled=None):
        usage = m.RuntimeUsage(kernel_calls=1, kernel_work=7, q_calls=1,
                               q_local=11, unit10_calls=1, unit10_units=13)
        caps = (("kernel_work", 100000), ("q_local", 20000), ("unit10_units", 200000))
        reply = m.FollowupResult(m.K100K_F_ID, request.identity, request,
            "GUESS_BLOCKED", "INJECTED_K100K", (), "EXACT_Q", "GUESS_BLOCKED",
            None, None, None, None, None, usage,
            tuple(m.Settlement(k, cap, getattr(usage, k), "SETTLED") for k, cap in caps), True, 0.0)
        if AUDIT:
            AUDIT.emit("k100k_injected_f", dict(request=request, result=reply,
                classification="controlled_response_not_real_F"))
        return reply

    def test_legacy_serialized_limits_identity_and_missing_fields(self):
        import json
        old_f = dict(kernel=dict(max_cells=480, max_constraints=2048, max_derived=1024,
                                 max_work=500000, max_seconds=2.0),
            plan=dict(max_pivots=12, max_targets=96, max_subsets=131072, max_seconds=1.0),
            q=dict(max_cells=480, local_work=20000, exact_work=200000, max_seconds=2.0,
                   counter_units=200000), max_seconds=5.0, kernel_kind="indexed")
        old_model = dict(samples=8, shortlist=4, rows=32, sampler_work=2000000,
            virtual_inputs=20000, row_inputs=512, f_lookups=16000, f_misses=4096,
            kernel_work=60000000, q_local=10000000, unit10_units=30000000,
            cache_entries=2048, max_seconds=30.0, root=dict(max_cells=480,
                max_generated=4096, max_candidates=2048, max_distinct_events=512,
                max_backend_calls=33, max_total_backend_work=500000, max_seconds=10.0),
            diagnostic=False, kernel_kind="indexed")
        for kind, fid in (("indexed", "PUBLIC_F_INDEXED_COVER_UNIT10_V1:prepaid_indexed_immutable_relations_v1:FA1K_U71"),
                          ("v1", "PUBLIC_F_V1_COVER_UNIT10_V1:prepaid_bounded_bitsets_v1:FA1K_U71")):
            with self.subTest(kind=kind):
                old_f["kernel_kind"] = old_model["kernel_kind"] = kind
                fq = replace(self.followup(), limits=m.fixed_followup_limits(kind))
                expected_f = dict(observation=((0, H),), num_mines=0, counted_inputs=1,
                    allow_guess=False, prior_id=m.PRIOR_ID, limits=old_f)
                self.assertEqual(json.dumps(m.exact_json(fq), sort_keys=True),
                                 json.dumps(m.exact_json(expected_f), sort_keys=True))
                self.assertEqual(fq.identity, m.public_digest((fid, expected_f)))
                self.assertEqual(fq.limits, m.FollowupLimits(kernel_kind=kind))
                q = m.ModelRequest(((0, H),), 0, 1, limits=m.ModelLimits(kernel_kind=kind))
                expected = dict(observation=((0, H),), num_mines=0, counted_inputs=1,
                    mode="S", allow_guess=False, target=None, planning_seed=0,
                    prior_id=m.PRIOR_ID, limits=old_model)
                self.assertEqual(q.identity, m.public_digest((
                    "RUNTIME_COMMON_POSTERIOR_THEN_PUBLIC_F_V5_ROOT_BASE_REUSE", expected)))
                self.assertEqual(m.ModelRequest.from_payload(q.to_payload()), q)
        self.assertEqual(m.ModelLimits.from_payload({}), m.ModelLimits())
        payload = m.ModelRequest(((0, H),), 0, 1).to_payload()
        del payload["limits"]["kernel_kind"]
        self.assertEqual(m.ModelRequest.from_payload(payload).limits, m.ModelLimits())

    def test_kind_validation_and_fixed_caps_reject_contradictions(self):
        fixed = m.fixed_followup_limits("indexed_k100k")
        self.assertEqual(fixed.followup_id,
            "PUBLIC_F_INDEXED_K100K_COVER_UNIT10_V1:prepaid_indexed_immutable_relations_v1:FA1K_U71")
        self.assertEqual(fixed.kernel, m.KernelLimits(max_work=100000))
        self.assertEqual((fixed.plan, fixed.q, fixed.max_seconds), (m.PlanLimits(), m.ExactLimits(), 5.0))
        q = replace(query(), limits=self.limits())
        self.assertEqual(m.ModelRequest.from_payload(q.to_payload()), q)
        for bad in (None, True, 1, "", "INDEXED_K100K", "indexed_k99999"):
            with self.subTest(bad=bad), self.assertRaises((TypeError, ValueError)):
                m.ModelLimits.from_payload({"kernel_kind": bad})
        with self.assertRaises(ValueError):
            m.FollowupLimits(kernel_kind="indexed_k100k")
        changes = [dict(kernel=m.KernelLimits(max_work=n)) for n in (0, 99999, 100001, 500000)]
        changes += [dict(kernel=replace(fixed.kernel, max_derived=1023)),
                    dict(kernel=replace(fixed.kernel, max_seconds=1.0)),
                    dict(plan=m.PlanLimits(max_subsets=1)), dict(plan=m.PlanLimits(max_seconds=0.5)),
                    dict(q=m.ExactLimits(local_work=19999)), dict(q=m.ExactLimits(counter_units=199999)),
                    dict(q=m.ExactLimits(max_seconds=1.0)), dict(max_seconds=4.999)]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(fixed, **change)
        for bad in (True, -1, 100000.0):
            with self.subTest(bad_cap=bad), self.assertRaises(ValueError):
                m.KernelLimits(max_work=bad)

    def test_real_small_models_use_one_fixed_F_and_score_identity(self):
        for mode in ("S", "M", "R"):
            q = replace(query("G001", mode), limits=self.limits())
            result = m.evaluate_model(q)
            self.assertEqual(result.status, "COMPLETE", result.error)
            self.assertEqual((result.model_id, result.followup_id), (m.MODEL_ID, m.K100K_F_ID))
            self.assertTrue(result.calls)
            self.assertTrue(result.scores)
            self.assertTrue(all(s.pilot_id == m.K100K_F_ID for s in result.scores))
            for call in result.calls:
                self.assertEqual(call.request.limits, m.fixed_followup_limits("indexed_k100k"))
                self.assertEqual(call.result.followup_id, m.K100K_F_ID)
                assert_reuse_binding(self, call)
                self.assertEqual(call.origin_request_id, call.result.request_id)
                if call.result.facts:
                    self.assertEqual(call.result.facts.work_version, m.WORK_VERSION)
            if AUDIT:
                AUDIT.emit("k100k_real_small", dict(request=q, result=result,
                    classification="real_small_exhaustive_model_not_performance_sample"))

    def test_cache_separates_F_identity_and_rejects_injected_other_F(self):
        fq = self.followup()
        baseline = replace(fq, limits=m.fixed_followup_limits("indexed"))
        self.assertNotEqual(fq.identity, baseline.identity)
        self.assertNotEqual(fq.logical_key, baseline.logical_key)
        self.assertNotEqual(fq.reuse_key, baseline.reuse_key)
        with patch.object(m, "perf_counter", return_value=100.0):
            budget = m._Budget(replace(query(), limits=self.limits()), None)
            cache, calls = m._FollowupCache(2), []
            with patch.object(m, "choose_followup", wraps=m.choose_followup) as backend:
                old = cache.choose(baseline, budget, calls)
                new = cache.choose(fq, budget, calls)
                self.assertEqual(backend.call_count, 2)
                self.assertEqual(new.followup_id, m.K100K_F_ID)
                self.assertIs(cache.choose(fq, budget, calls), new)
                self.assertEqual(backend.call_count, 2)
            cache.entries[fq.reuse_key] = old
            with patch.object(m, "choose_followup") as backend, self.assertRaisesRegex(ValueError, "INVALID_CACHED_F"):
                cache.choose(fq, budget, calls)
            backend.assert_not_called()

    def test_full_reservation_99999_100000_Q_unit10_and_time(self):
        caps = (("kernel_work", 100000, "KERNEL_BUDGET"),
                ("q_local", 20000, "Q_LOCAL_BUDGET"), ("unit10_units", 200000, "UNIT10_BUDGET"))
        with patch.object(m, "perf_counter", return_value=100.0):
            for resource, cap, reason in caps:
                for delta in (-1, 0, 1):
                    with self.subTest(resource=resource, remaining=cap+delta):
                        budget = m._Budget(replace(query(), limits=self.limits(**{resource: cap+delta})), None)
                        cache, calls = m._FollowupCache(1), []
                        with patch.object(m, "choose_followup", side_effect=self.fake) as backend:
                            if delta < 0:
                                with self.assertRaises(m._Stop) as stopped:
                                    cache.choose(self.followup(), budget, calls)
                                self.assertEqual(stopped.exception.reason, reason)
                                self.assertEqual((calls, budget.settlements, budget.usage.f_misses), ([], [], 0))
                                backend.assert_not_called()
                            else:
                                cache.choose(self.followup(), budget, calls)
                                self.assertEqual(backend.call_count, 1)
                                self.assertEqual(backend.call_args.args[0].limits, self.followup().limits)
                                self.assertEqual([s.reserved for s in budget.settlements], [100000, 20000, 200000])
            for seconds in (4.999, 5.0, 5.001):
                budget = m._Budget(replace(query(), limits=self.limits()), None)
                budget.deadline = 100.0+seconds
                cache, calls = m._FollowupCache(1), []
                with patch.object(m, "choose_followup", side_effect=self.fake) as backend:
                    if seconds < 5:
                        with self.assertRaises(m._Stop) as stopped:
                            cache.choose(self.followup(), budget, calls)
                        self.assertEqual(stopped.exception.reason, "F_TIME_RESERVATION")
                        self.assertEqual((calls, budget.settlements, backend.call_count), ([], [], 0))
                    else:
                        cache.choose(self.followup(), budget, calls)
                        self.assertEqual(backend.call_count, 1)

    def test_atomic_limits_cancel_exception_and_unknown_accounting(self):
        q = replace(query(), limits=self.limits())
        for limits in (self.limits(kernel_work=99999), self.limits(row_inputs=0), self.limits(f_misses=0)):
            result = m.evaluate_model(replace(q, limits=limits))
            self.assertEqual(result.status, "RESOURCE_LIMIT")
            self.assertEqual((result.sequence, result.scores, result.selected_candidate_id), ((), (), None))
            for row in result.rows:
                if row.outcome in ("NOT_STARTED", "UNRESOLVED"):
                    self.assertEqual((row.value_x, row.hit, row.virtual_b), (None, None, None))
        self.assertEqual(m.evaluate_model(q, cancelled=lambda: True).status, "CANCELLED")
        self.assertEqual(m.evaluate_model(q, cancelled=lambda: 1).status, "ERROR")
        with patch.object(m, "choose_followup", side_effect=RuntimeError("injected after reservation")):
            result = m.evaluate_model(q)
        self.assertEqual((result.status, result.sequence, result.scores), ("ERROR", (), ()))
        self.assertFalse(result.usage.accounting_complete)
        unknown = [s for s in result.settlements if s.status == "UNKNOWN_SPEND"]
        self.assertEqual([(s.resource, s.reserved, s.actual) for s in unknown],
            [("kernel_work", 100000, None), ("q_local", 20000, None), ("unit10_units", 200000, None)])

    def test_partial_matrix_keeps_terminal_rows_without_scores(self):
        original_row, finished = m._row, []
        def exhaust(*args):
            row, stopped = original_row(*args)
            if not finished:
                self.assertIsNone(stopped)
                self.assertIsNotNone(row.value_x)
                finished.append(row)
                budget = args[4]
                budget.usage = replace(budget.usage, kernel_work=budget.request.limits.kernel_work)
            return row, stopped
        with patch.object(m, "perf_counter", return_value=100.0), patch.object(m, "_row", side_effect=exhaust):
            result = m.evaluate_model(replace(query(), limits=self.limits(cache_entries=0)))
        self.assertEqual((result.status, result.reason), ("RESOURCE_LIMIT", "KERNEL_BUDGET"))
        self.assertEqual(result.rows[0], finished[0])
        self.assertEqual((result.sequence, result.scores, result.selected_candidate_id), ((), (), None))
        self.assertTrue(any(r.outcome == "UNRESOLVED" and r.value_x is None for r in result.rows))

    def test_incomplete_indexed_kernel_passes_same_public_state_to_Q(self):
        from stage4_public_kernel import KernelResult
        fq = self.followup()
        # Controlled kernel replies test routing; B separately measures real work limits.
        for status in ("WORK_LIMIT", "DERIVED_LIMIT"):
            def limited(kr, **kwargs):
                self.assertEqual(kr.limits, m.KernelLimits(max_work=100000))
                return KernelResult("STAGE4_PUBLIC_KERNEL", kr.version, kr.identity,
                    status, status, (), (), (), None, 100000, (), m.WORK_VERSION, 0, 0, 0, 0.0)
            seen = []
            original = m.ExactPilot.choose
            def q_spy(owner, request, **kwargs):
                seen.append(request)
                return original(owner, request, **kwargs)
            with patch.object(m, "infer_public_indexed", side_effect=limited) as indexed, \
                    patch.object(m, "infer_public") as v1, patch.object(m, "plan_safe") as plan, \
                    patch.object(m.ExactPilot, "choose", q_spy):
                result = m.choose_followup(fq)
            self.assertEqual(indexed.call_count, 1)
            v1.assert_not_called()
            plan.assert_not_called()
            self.assertEqual((result.status, result.source, result.followup_id), ("READY", "EXACT_Q", m.K100K_F_ID))
            self.assertEqual(len(seen), 1)
            self.assertEqual((seen[0].observation, seen[0].num_mines, seen[0].counted_inputs,
                seen[0].allow_guess, seen[0].prior_id),
                (fq.observation, fq.num_mines, fq.counted_inputs, fq.allow_guess, fq.prior_id))
            self.assertEqual((result.facts.proven_safe, result.facts.proven_mines,
                              result.facts.constraints, result.facts.proof_id), ((), (), (), None))


class ObservationReuseTests(unittest.TestCase):
    """S4_F_OBS_MEMO1: inside one model call a public state is given to F once.

    counted_inputs alone no longer forces a second F run. Injected F replies are
    labelled as such; the real cases use the product F on small exhaustive grids.
    """
    RESOURCES = ("kernel_work", "q_local", "unit10_units")

    def followup(self, counted=1, grid=((0, H),), **kwargs):
        return m.FollowupRequest(grid, 0, counted, False, **kwargs)

    def fake(self, request, *, cancelled=None):
        usage = m.RuntimeUsage(kernel_calls=1, kernel_work=7, q_calls=1,
                               q_local=11, unit10_calls=1, unit10_units=13)
        caps = (("kernel_work", request.limits.kernel.max_work), ("q_local", request.limits.q.local_work),
                ("unit10_units", request.limits.q.counter_units))
        return m.FollowupResult(request.limits.followup_id, request.identity, request,
            "GUESS_BLOCKED", "INJECTED_COMPLETE", (), "EXACT_Q", "GUESS_BLOCKED",
            None, None, None, None, None, usage,
            tuple(m.Settlement(name, cap, getattr(usage, name), "SETTLED") for name, cap in caps), True, 0.0)

    def others(self, base):
        """Requests that differ from base in something F reads."""
        return {
            "observation": self.followup(base.counted_inputs, ((H, 0),)),
            "num_mines": m.FollowupRequest(base.observation, 1, base.counted_inputs, False),
            "allow_guess": replace(base, allow_guess=True),
            "kind_v1": replace(base, limits=m.FollowupLimits(kernel_kind="v1")),
            "kind_k100k": replace(base, limits=m.fixed_followup_limits("indexed_k100k")),
            "kernel_cap": replace(base, limits=replace(base.limits, kernel=m.KernelLimits(max_work=499_999))),
            "plan_cap": replace(base, limits=replace(base.limits, plan=m.PlanLimits(max_subsets=1))),
            "q_cap": replace(base, limits=replace(base.limits, q=m.ExactLimits(counter_units=199_999))),
        }

    def test_reuse_key_leaves_out_counted_inputs_only(self):
        base = self.followup(7)
        self.assertEqual([item for item in base.logical_key if item not in base.reuse_key], [7])
        self.assertEqual(len(base.reuse_key), len(base.logical_key)-1)
        for counted in (0, 1, 8, 4096):
            other = replace(base, counted_inputs=counted)
            self.assertEqual(base.reuse_key, other.reuse_key)
            self.assertNotEqual(base.logical_key, other.logical_key)   # still a different request
            self.assertNotEqual(base.identity, other.identity)
        others = self.others(base)
        self.assertEqual(len({base.reuse_key} | {o.reuse_key for o in others.values()}), len(others)+1)
        for name, other in others.items():
            with self.subTest(other=name):
                self.assertNotEqual(base.reuse_key, replace(other, counted_inputs=3).reuse_key)
        # Wall-time caps were outside the logical key before and stay outside both keys.
        slow = replace(base, limits=replace(base.limits, max_seconds=1.0))
        self.assertEqual((base.reuse_key, base.logical_key), (slow.reuse_key, slow.logical_key))

    def test_current_request_is_validated_before_any_reuse(self):
        for bad in (-1, True, 1.0, "2", None):
            with self.subTest(bad=bad), self.assertRaises((TypeError, ValueError)):
                self.followup(bad)

    def test_same_public_state_is_computed_once_for_any_counted_total(self):
        # New requirement: fails before S4_F_OBS_MEMO1 (three F runs), passes after (one).
        with patch.object(m, "perf_counter", return_value=100.0):
            budget, cache, calls = m._Budget(query(), None), m._FollowupCache(4), []
            with patch.object(m, "choose_followup", side_effect=self.fake) as backend:
                results = [cache.choose(self.followup(counted), budget, calls) for counted in (1, 2, 9)]
            self.assertEqual(backend.call_count, 1)
            self.assertIs(results[1], results[0])
            self.assertIs(results[2], results[0])
            self.assertEqual((budget.usage.f_lookups, budget.usage.f_misses, budget.usage.f_hits), (3, 1, 2))
            self.assertEqual((budget.usage.kernel_work, budget.usage.q_local, budget.usage.unit10_units), (7, 11, 13))

    def test_reuse_returns_the_original_result_and_records_the_lookup(self):
        with patch.object(m, "perf_counter", return_value=100.0):
            budget = m._Budget(query(), None)
            cache, calls, first = m._FollowupCache(4), [], self.followup(1)
            with patch.object(m, "choose_followup", side_effect=self.fake) as backend:
                original = cache.choose(first, budget, calls)
                # No work and no five seconds are left: only a reuse can answer now.
                budget.usage = replace(budget.usage, **{name: getattr(TINY, name) for name in self.RESOURCES})
                budget.deadline = 100.001
                before, settlements = budget.usage, tuple(budget.settlements)
                later = self.followup(2)
                self.assertNotEqual(later.identity, first.identity)
                self.assertIs(cache.choose(later, budget, calls), original)
                self.assertIs(cache.choose(self.followup(9), budget, calls), original)
                self.assertIs(cache.choose(self.followup(1), budget, calls), original)
                self.assertEqual(backend.call_count, 1)
            self.assertEqual([c.cache_hit for c in calls], [False, True, True, True])
            self.assertEqual([c.reuse for c in calls],
                             ["MISS", "OBSERVATION_EQUIVALENT", "OBSERVATION_EQUIVALENT", "SAME_REQUEST"])
            # The record names the current lookup; the result stays the original one.
            self.assertEqual([c.request.counted_inputs for c in calls], [1, 2, 9, 1])
            for call in calls:
                self.assertIs(call.result, original)
                self.assertEqual(call.result.request.counted_inputs, 1)
                self.assertEqual(call.origin_request_id, first.identity)
                self.assertEqual(call.result.request_id, first.identity)
                assert_reuse_binding(self, call)
            self.assertEqual(calls[1].request, later)
            self.assertNotEqual(calls[1].request.identity, calls[1].origin_request_id)
            self.assertEqual(original.request, first)
            self.assertEqual((budget.usage.f_lookups, budget.usage.f_misses, budget.usage.f_hits), (4, 1, 3))
            for resource in self.RESOURCES:
                self.assertEqual(getattr(budget.usage, resource), getattr(before, resource))
            self.assertEqual(tuple(budget.settlements), settlements)
            self.assertEqual(len(cache.entries), 1)

    def test_real_reuse_keeps_the_proof_bound_to_its_original_request(self):
        from stage4_public_kernel import verify_facts
        budget, cache, calls = m._Budget(query(), None), m._FollowupCache(4), []
        first, later = self.followup(1), self.followup(5)
        original = cache.choose(first, budget, calls)
        self.assertEqual((original.status, original.source), ("READY", "PUBLIC_KERNEL"), original.error)
        reused = cache.choose(later, budget, calls)
        self.assertIs(reused, original)
        self.assertEqual(calls[-1].reuse, "OBSERVATION_EQUIVALENT")
        # The certificate is the original request's and verifies for that request.
        self.assertEqual(reused.request_id, first.identity)
        self.assertEqual(reused.kernel_request.counted_inputs, 1)
        self.assertEqual(reused.facts.request_id, reused.kernel_request.identity)
        self.assertEqual((reused.plan.request_id, reused.plan.proof_id),
                         (reused.kernel_request.identity, reused.facts.proof_id))
        verify_facts(reused.kernel_request, reused.facts)
        # A direct F run for the later request decides and proves the same, under its own identities.
        direct = m.choose_followup(later)
        self.assertEqual((direct.status, direct.reason, direct.source, direct.sequence, direct.terminal_outcome),
                         (reused.status, reused.reason, reused.source, reused.sequence, reused.terminal_outcome))
        self.assertEqual((direct.facts.proven_safe, direct.facts.proven_mines, direct.facts.constraints,
                          direct.facts.work, direct.facts.work_by_family),
                         (reused.facts.proven_safe, reused.facts.proven_mines, reused.facts.constraints,
                          reused.facts.work, reused.facts.work_by_family))
        self.assertEqual(direct.usage, reused.usage)
        self.assertEqual(direct.kernel_request.counted_inputs, 5)
        self.assertNotEqual(direct.request_id, reused.request_id)
        self.assertNotEqual(direct.facts.request_id, reused.facts.request_id)
        self.assertNotEqual(direct.facts.proof_id, reused.facts.proof_id)
        verify_facts(direct.kernel_request, direct.facts)
        # The reused proof is never valid as a proof for the later request.
        with self.assertRaisesRegex(ValueError, "FACT_IDENTITY"):
            verify_facts(direct.kernel_request, reused.facts)

    def test_other_state_setting_kind_or_cap_is_never_a_hit(self):
        with patch.object(m, "perf_counter", return_value=100.0):
            base = self.followup(1)
            others = self.others(base)
            budget, cache, calls = m._Budget(query(), None), m._FollowupCache(16), []
            with patch.object(m, "choose_followup", side_effect=self.fake) as backend:
                cache.choose(base, budget, calls)
                for count, (name, other) in enumerate(others.items(), 2):
                    with self.subTest(other=name):
                        cache.choose(replace(other, counted_inputs=3), budget, calls)
                        self.assertEqual(backend.call_count, count)
                        self.assertFalse(calls[-1].cache_hit)
                        self.assertEqual(calls[-1].result.request_id, calls[-1].request.identity)
                # Each of them is reusable for its own public state and setting only.
                for name, other in others.items():
                    with self.subTest(reuse=name):
                        result = cache.choose(replace(other, counted_inputs=8), budget, calls)
                        self.assertEqual(calls[-1].reuse, "OBSERVATION_EQUIVALENT")
                        self.assertEqual(result.request.reuse_key, other.reuse_key)
                self.assertEqual(backend.call_count, len(others)+1)

    def test_reuse_hit_obeys_current_cancel_deadline_and_lookup_cap(self):
        with patch.object(m, "perf_counter", return_value=100.0):
            first, later = self.followup(1), self.followup(2)
            original = self.fake(first, cancelled=lambda: False)
            reasons = {"cancel": "CANCELLED", "deadline": "TIME_LIMIT",
                       "zero_f_seconds": "CURRENT_F_DEADLINE", "lookup_cap": "F_LOOKUPS_LIMIT"}
            for kind in ("cancel", "bad_callback", "callback_error", "deadline", "zero_f_seconds", "lookup_cap"):
                with self.subTest(kind=kind):
                    def cancel():
                        if kind == "callback_error":
                            raise RuntimeError("injected external error")
                        return 1 if kind == "bad_callback" else kind == "cancel"
                    limits = replace(TINY, kernel_work=0, f_lookups=0 if kind == "lookup_cap" else TINY.f_lookups)
                    budget = m._Budget(replace(query(), limits=limits), cancel)
                    if kind == "deadline":
                        budget.deadline = 100.0
                    cache, calls = m._FollowupCache(1), []
                    cache.entries[first.reuse_key] = original
                    lookup = (replace(later, limits=replace(later.limits, max_seconds=0.0))
                              if kind == "zero_f_seconds" else later)
                    self.assertEqual(lookup.reuse_key, first.reuse_key)
                    with patch.object(m, "choose_followup") as backend:
                        expected = (TypeError if kind == "bad_callback" else
                                    RuntimeError if kind == "callback_error" else m._Stop)
                        with self.assertRaises(expected) as raised:
                            cache.choose(lookup, budget, calls)
                        if kind in reasons:
                            self.assertEqual(raised.exception.reason, reasons[kind])
                        backend.assert_not_called()
                    self.assertFalse(calls)
                    self.assertEqual(budget.usage.f_hits, 0)
            # Without any of those constraints the same entry does answer the later request.
            budget = m._Budget(replace(query(), limits=replace(TINY, kernel_work=0)), None)
            cache, calls = m._FollowupCache(1), []
            cache.entries[first.reuse_key] = original
            with patch.object(m, "choose_followup") as backend:
                self.assertIs(cache.choose(later, budget, calls), original)
                backend.assert_not_called()

    def test_new_state_after_reuse_still_needs_the_full_reservation(self):
        with patch.object(m, "perf_counter", return_value=100.0):
            for resource, reason in (("kernel_work", "KERNEL_BUDGET"), ("q_local", "Q_LOCAL_BUDGET"),
                                     ("unit10_units", "UNIT10_BUDGET"), (None, "F_TIME_RESERVATION")):
                with self.subTest(gate=reason):
                    budget, cache, calls = m._Budget(query(), None), m._FollowupCache(4), []
                    with patch.object(m, "choose_followup", side_effect=self.fake) as backend:
                        cache.choose(self.followup(1), budget, calls)
                        cache.choose(self.followup(2), budget, calls)          # reuse
                        self.assertEqual(backend.call_count, 1)
                        if resource is None:
                            budget.deadline = 100.0+4.999
                        else:
                            cap = getattr(self.followup().limits.kernel if resource == "kernel_work"
                                          else self.followup().limits.q,
                                          {"kernel_work": "max_work", "q_local": "local_work",
                                           "unit10_units": "counter_units"}[resource])
                            budget.usage = replace(budget.usage, **{resource: getattr(TINY, resource)-cap+1})
                        settled = tuple(budget.settlements)
                        with self.assertRaises(m._Stop) as stopped:
                            cache.choose(self.followup(3, ((H, 0),)), budget, calls)
                        self.assertEqual((stopped.exception.status, stopped.exception.reason),
                                         ("RESOURCE_LIMIT", reason))
                        self.assertEqual(backend.call_count, 1)
                        self.assertEqual((budget.usage.f_misses, len(calls), tuple(budget.settlements)),
                                         (1, 2, settled))
                        # The already computed state is still answered without a reservation.
                        cache.choose(self.followup(4), budget, calls)
                        self.assertEqual((backend.call_count, calls[-1].reuse), (1, "OBSERVATION_EQUIVALENT"))

    def test_reuse_rejects_tampered_or_foreign_entries(self):
        with patch.object(m, "perf_counter", return_value=100.0):
            first, later = self.followup(1), self.followup(2)
            original = self.fake(first, cancelled=lambda: False)
            foreign = self.followup(1, ((H, 0),))
            guessing = replace(first, allow_guess=True)
            other_kind = replace(first, limits=m.fixed_followup_limits("indexed_k100k"))
            variants = {
                # rewritten to look as if it had been computed for the current request
                "relabelled_as_current": replace(original, request_id=later.identity),
                "request_id": replace(original, request_id="wrong"),
                "foreign_state": replace(original, request=foreign, request_id=foreign.identity),
                "guess_setting": replace(original, request=guessing, request_id=guessing.identity),
                "other_kind_request": replace(original, request=other_kind, request_id=other_kind.identity),
                "followup_id": replace(original, followup_id=m.K100K_F_ID),
                "incomplete": replace(original, status="RESOURCE_LIMIT"),
                "cancelled": replace(original, status="CANCELLED"),
                "uncacheable": replace(original, cacheable=False),
                "error": replace(original, error="backend error"),
                "unknown_usage": replace(original, usage=replace(original.usage, accounting_complete=False)),
                "unknown_settlement": replace(original,
                    settlements=(m.Settlement("kernel_work", 500000, None, "UNKNOWN_SPEND"),)),
                "wrong_total": replace(original, usage=replace(original.usage, kernel_work=8)),
                "over_cap": replace(original, settlements=(m.Settlement("kernel_work", 500001, 7, "SETTLED"),)
                                    + original.settlements[1:]),
                "foreign_resource": replace(original, settlements=original.settlements
                                            + (m.Settlement("sampler_work", 1, 0, "SETTLED"),)),
            }
            for name, result in variants.items():
                with self.subTest(name=name):
                    budget, cache, calls = m._Budget(query(), None), m._FollowupCache(1), []
                    cache.entries[later.reuse_key] = result
                    with patch.object(m, "choose_followup") as backend, self.assertRaises(ValueError):
                        cache.choose(later, budget, calls)
                    backend.assert_not_called()
                    self.assertFalse(calls)
                    self.assertEqual(budget.usage.f_hits, 0)
            budget, cache, calls = m._Budget(query(), None), m._FollowupCache(1), []
            cache.entries[later.reuse_key] = original
            with patch.object(m, "choose_followup") as backend:
                self.assertIs(cache.choose(later, budget, calls), original)
                backend.assert_not_called()

    def test_time_limited_or_failed_F_result_is_never_stored_or_reused(self):
        # A result reached through a wall-time fallback, a cancellation or an error is not
        # a completed logical choice: no later request may reuse it, whatever its total.
        with patch.object(m, "perf_counter", return_value=100.0):
            for kind, status in (("time_fallback", "READY"), ("cancelled", "CANCELLED"), ("error", "ERROR")):
                with self.subTest(kind=kind):
                    def backend(request, **kwargs):
                        return replace(self.fake(request, **kwargs), status=status,
                                       reason="INJECTED_" + kind.upper(), cacheable=False)
                    budget, cache, calls = m._Budget(query(), None), m._FollowupCache(4), []
                    with patch.object(m, "choose_followup", side_effect=backend) as spy:
                        cache.choose(self.followup(1), budget, calls)
                        self.assertFalse(cache.entries)
                        cache.choose(self.followup(2), budget, calls)     # same state, another total
                        cache.choose(self.followup(1), budget, calls)     # even the same request
                        self.assertEqual(spy.call_count, 3)
                    self.assertEqual([c.cache_hit for c in calls], [False, False, False])
                    self.assertEqual((budget.usage.f_misses, budget.usage.f_hits, budget.usage.kernel_work), (3, 0, 21))
                    self.assertFalse(cache.entries)

    def test_cache_lives_for_one_model_call_and_keeps_its_capacity(self):
        made = []

        class Recording(m._FollowupCache):
            def __init__(self, capacity):
                super().__init__(capacity)
                made.append(self)

        with patch.object(m, "_FollowupCache", Recording):
            first = m.evaluate_model(query())
            second = m.evaluate_model(query())
        self.assertEqual((first.status, second.status), ("COMPLETE", "COMPLETE"), (first.error, second.error))
        self.assertEqual(len(made), 2)
        self.assertIsNot(made[0], made[1])
        self.assertTrue(all(not cache.entries for cache in made))       # cleared when the call returns
        self.assertFalse(second.calls[0].cache_hit)                     # nothing is carried over
        self.assertEqual((first.rows, first.scores, first.usage), (second.rows, second.scores, second.usage))
        with patch.object(m, "perf_counter", return_value=100.0):
            state_a, state_b = ((0, H),), ((H, 0),)
            for capacity, expected in ((0, 4), (1, 4), (2, 2)):
                with self.subTest(capacity=capacity):
                    budget, cache, calls = m._Budget(query(), None), m._FollowupCache(capacity), []
                    with patch.object(m, "choose_followup", side_effect=self.fake) as backend:
                        for counted, grid in ((1, state_a), (2, state_b), (3, state_a), (4, state_b)):
                            cache.choose(self.followup(counted, grid), budget, calls)
                        self.assertEqual(backend.call_count, expected)
                    self.assertLessEqual(len(cache.entries), capacity)
                    self.assertEqual(budget.usage.cache_peak, capacity)
                    self.assertEqual(budget.usage.f_misses, expected)
                    self.assertEqual(budget.usage.f_hits, 4-expected)

    def test_rows_are_scored_with_their_own_counted_inputs(self):
        reused = 0
        for name, (grid, prefix) in WITNESSES.items():
            for mode in ("S", "M", "R"):
                q = query(name, mode)
                result = m.evaluate_model(q)
                self.assertEqual(result.status, "COMPLETE", result.error)
                for row in result.rows:
                    sample = result.posterior.samples[row.sample_index]
                    replay = oracle.replay(grid, 1, sample.mines,
                        [(a.action, a.x, a.y) for a in row.actions], prefix)
                    self.assertEqual((replay["outcome"], replay["X"], replay["added_inputs"]),
                                     (row.outcome, row.value_x, row.added_inputs))
                    if row.outcome == "WON":
                        self.assertEqual(row.value_x, Fraction(row.virtual_b, prefix+row.added_inputs))
                    for index in row.f_call_indices:
                        call = result.calls[index]
                        assert_reuse_binding(self, call)
                        if call.reuse == "OBSERVATION_EQUIVALENT":
                            reused += 1
                            # The stored request's total is another row's; it is never this row's cost.
                            self.assertNotEqual(call.request.counted_inputs, call.result.request.counted_inputs)
                            self.assertLessEqual(call.request.counted_inputs, prefix+row.added_inputs)
        self.assertGreater(reused, 0)

    def test_reuse_changes_work_but_not_rows_scores_or_selection(self):
        saved = 0
        for name in WITNESSES:
            for mode in ("S", "M", "R"):
                q = query(name, mode)
                reuse = m.evaluate_model(q)
                # Control: the key as it was before S4_F_OBS_MEMO1 (counted_inputs included).
                with patch.object(m.FollowupRequest, "reuse_key", m.FollowupRequest.logical_key):
                    strict = m.evaluate_model(q)
                self.assertEqual((reuse.status, strict.status), ("COMPLETE", "COMPLETE"), (reuse.error, strict.error))
                self.assertEqual((reuse.rows, reuse.scores, reuse.sequence, reuse.selected_candidate_id,
                                  reuse.posterior.samples, reuse.target_status),
                                 (strict.rows, strict.scores, strict.sequence, strict.selected_candidate_id,
                                  strict.posterior.samples, strict.target_status))
                self.assertEqual(reuse.usage.f_lookups, strict.usage.f_lookups)
                self.assertLessEqual(reuse.usage.f_misses, strict.usage.f_misses)
                for result in (reuse, strict):
                    # Every F run is charged exactly once; a hit charges nothing.
                    ran = [call.result for call in result.calls if not call.cache_hit]
                    self.assertEqual(result.usage.f_lookups, result.usage.f_hits+result.usage.f_misses)
                    self.assertEqual(result.usage.f_misses, len(ran))
                    self.assertEqual(result.usage.kernel_calls, sum(r.usage.kernel_calls for r in ran))
                    self.assertEqual(result.usage.q_calls, sum(r.usage.q_calls for r in ran))
                    for resource in self.RESOURCES:
                        self.assertEqual(getattr(result.usage, resource), sum(getattr(r.usage, resource) for r in ran))
                        self.assertEqual(getattr(result.usage, resource),
                                         sum(s.actual for s in result.settlements if s.resource == resource))
                    self.assertTrue(result.usage.accounting_complete)
                    self.assertTrue(all(c.reuse != "OBSERVATION_EQUIVALENT" for c in strict.calls))
                for resource in self.RESOURCES:
                    self.assertLessEqual(getattr(reuse.usage, resource), getattr(strict.usage, resource))
                saved += strict.usage.f_misses-reuse.usage.f_misses
        self.assertGreater(saved, 0)

    def test_direct_F_for_real_inputs_keeps_the_full_request_binding(self):
        import stage4_runtime_policy as p
        grid, prefix = WITNESSES["G001"]
        request = p.RuntimeRequest(grid, 1, prefix, "M", True, limits=p.RuntimeLimits(max_model_attempts=0))
        real = m.choose_followup

        def other_total(fq, **kwargs):
            # The same public state decided at another counted total and relabelled
            # with the current request id: the direct path must still refuse it.
            foreign = real(replace(fq, counted_inputs=fq.counted_inputs+1), **kwargs)
            return replace(foreign, request_id=fq.identity)

        for backend, expected in ((real, "HEURISTIC_FALLBACK"), (other_total, "ERROR")):
            with self.subTest(expected=expected):
                policy = p.RuntimePolicy()
                try:
                    with patch.object(p, "choose_followup", side_effect=backend):
                        result = policy.choose(request)
                finally:
                    policy.close()
                self.assertEqual(result.status, expected, (result.reason, result.error))
                self.assertFalse(result.model_attempted)
                if expected == "ERROR":
                    self.assertEqual((result.sequence, result.proposal_id), ((), None))
                    self.assertIn("F_BINDING_OR_UNKNOWN_ACCOUNTING", result.error)
                else:
                    self.assertEqual(result.followup.request.counted_inputs, prefix)
                    self.assertEqual(result.followup.request_id, result.followup.request.identity)


if __name__ == "__main__":
    unittest.main()
