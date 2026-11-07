"""Standalone API, accounting, memory, and atomic publication boundaries."""
from dataclasses import FrozenInstanceError, fields, replace
from fractions import Fraction
import json
from math import comb
import unittest
from unittest.mock import patch

import stage4_belief_counter as counter
from stage4_belief_counter import CountLimits, CountRequest, CountResult, count_base


def pair(**limits):
    return CountRequest([[-2, 1, -2]], 1, limits=CountLimits(**limits))


class CounterTests(unittest.TestCase):
    # The bounded verification driver supplies the same entry point with durable receipts.
    invoke = staticmethod(count_base)

    def assert_stopped(self, r, status, reason):
        self.assertEqual((r.status, r.reason, r.base.status, r.base.reason),
                         (status, reason, status, reason))
        self.assertIsNone(r.base.marginals)
        self.assertIsNone(r.base.total_worlds)

    def test_public_payload_and_types(self):
        grid = [[-3, 1, -2]]
        req = CountRequest(grid, 1)
        grid[0][0] = 7
        self.assertEqual(req.observation, ((-3, 1, -2),))
        self.assertEqual(set(req.to_payload()), {"observation", "num_mines", "prior_id", "limits"})
        self.assertEqual(CountRequest.from_payload(json.loads(json.dumps(req.to_payload()))), req)
        self.assertRaises(FrozenInstanceError, setattr, req, "num_mines", 0)
        for forbidden in ("events", "layout", "seed", "3BV", "ZiNi", "active", "wasted",
                          "C", "mode", "target", "rank", "replay", "future"):
            with self.subTest(forbidden=forbidden), self.assertRaises(ValueError):
                CountRequest.from_payload(dict(req.to_payload(), **{forbidden: []}))
        with self.assertRaises(TypeError):
            self.invoke(None)
        with self.assertRaises(TypeError):
            self.invoke(pair(max_cells=0), cancelled=False)
        for grid in ([], [[-1]], [[True]], [[9]], [[0], [0, 0]]):
            with self.assertRaises(ValueError):
                CountRequest(grid, 0)
        for bad in (True, 0.5, -1, 2):
            with self.assertRaises(ValueError):
                CountRequest([[-2]], bad)
        for key, bad in (("limits", {}), ("prior_id", 1)):
            with self.assertRaises(TypeError):
                CountRequest([[-2]], 1, **{key: bad})
        self.assertRaises(TypeError, CountRequest.from_payload, [])
        self.assertRaises(TypeError, CountRequest.from_payload, dict(req.to_payload(), limits=[]))
        self.assertRaises(ValueError, CountLimits.from_payload, {"max_work": 10})

    def test_limits_and_identity(self):
        self.assertEqual(CountLimits().to_payload(),
                         dict(max_cells=480, max_total_work=200000, max_seconds=2.0,
                              memo_entries=16384, memo_scalars=1000000))
        for f in fields(CountLimits):
            cap = getattr(CountLimits(), f.name)
            bad = [True, -1, cap + 1, "1"]
            bad += [float("nan"), float("inf"), 10**400] if f.name == "max_seconds" else [1.0]
            for value in bad:
                with self.subTest(field=f.name, value=value), self.assertRaises(ValueError):
                    CountLimits(**{f.name: value})
            self.assertEqual(getattr(CountLimits(**{f.name: 0}), f.name), 0)
        public = pair()
        limited = replace(public, limits=CountLimits(memo_scalars=0))
        self.assertEqual(public.problem_id, limited.problem_id)
        self.assertNotEqual(public.request_id, limited.request_id)
        from_int = pair(max_seconds=2)
        self.assertIs(type(from_int.to_payload()["limits"]["max_seconds"]), float)
        self.assertEqual(from_int.request_id, pair(max_seconds=2.0).request_id)
        for changed in (replace(public, num_mines=2), replace(public, prior_id="other")):
            self.assertNotEqual(public.problem_id, changed.problem_id)
            self.assertNotEqual(public.request_id, changed.request_id)

    def test_flag_and_result_boundary(self):
        hidden = pair()
        flagged = replace(hidden, observation=[[-3, 1, -2]])
        self.assertNotEqual(hidden.problem_id, flagged.problem_id)
        self.assertNotEqual(hidden.request_id, flagged.request_id)
        a, b = self.invoke(hidden), self.invoke(flagged)
        self.assertIs(type(b), CountResult)
        self.assertEqual((a.status, b.status), ("COMPLETE", "COMPLETE"))
        self.assertEqual(a.base, b.base)
        self.assertEqual([c.probability for c in b.base.marginals], [Fraction(1, 2)]*2)
        data = b.to_dict()
        self.assertEqual(set(data), {"request_id", "problem_id", "backend_version",
                                     "work_accounting_version", "status", "reason", "base", "diagnostics"})
        self.assertEqual(data["base"]["total_worlds"], "2")
        self.assertEqual(data["base"]["marginals"][0]["probability"], {"numerator":"1","denominator":"2"})
        self.assertEqual((b.problem_id, b.request_id), (flagged.problem_id, flagged.request_id))

    def test_support_callback_time_work_order(self):
        calls = []
        def forbidden():
            calls.append(1)
            raise AssertionError("unsupported callback")
        limits = CountLimits(max_cells=0, max_total_work=0, max_seconds=0)
        request = replace(pair(), prior_id="unknown", limits=limits)
        self.assert_stopped(self.invoke(request, cancelled=forbidden), "UNSUPPORTED", "CELL_LIMIT")
        self.assert_stopped(self.invoke(replace(request, limits=replace(limits, max_cells=480)),
                                        cancelled=forbidden), "UNSUPPORTED", "PRIOR_UNSUPPORTED")
        self.assert_stopped(self.invoke(CountRequest([[-2]*481], 0), cancelled=forbidden),
                            "UNSUPPORTED", "CELL_LIMIT")
        self.assertEqual(calls, [])
        req = pair(max_total_work=0, max_seconds=0)
        def fail():
            raise RuntimeError("callback failure")
        for callback in (lambda: 1, fail):
            r = self.invoke(req, cancelled=callback)
            self.assert_stopped(r, "ERROR", "CANCEL_CALLBACK_ERROR")
            self.assertIsNotNone(r.diagnostics.error)
        self.assert_stopped(self.invoke(req, cancelled=lambda: True), "CANCELLED", "CANCELLED")
        self.assert_stopped(self.invoke(req, cancelled=lambda: False), "INSUFFICIENT", "TIME_LIMIT")
        for cap in (0, 1):
            r = self.invoke(pair(max_total_work=cap))
            self.assert_stopped(r, "INSUFFICIENT", "WORK_LIMIT")
            self.assertLessEqual(r.diagnostics.units_total, cap)

    def test_every_work_family_hits_real_cap(self):
        req = pair()
        full = self.invoke(req)
        self.assertEqual(full.status, "COMPLETE")
        d = full.diagnostics
        primary = ("forced_assignments", "branch_attempts", "dp_products")
        aux = ("preparation_visits", "constraint_visits", "constraint_cell_visits",
               "memo_operations", "histogram_updates", "publish_visits")
        self.assertEqual(sum(getattr(d, k) for k in primary), d.primary_work)
        self.assertEqual(sum(getattr(d, k) for k in aux), d.auxiliary_work)
        self.assertEqual(d.units_total, d.primary_work + d.auxiliary_work)
        self.assertTrue(all(getattr(d, k) > 0 for k in primary + aux))
        self.assertEqual(self.invoke(pair(max_total_work=d.units_total)).base, full.base)
        seen = set()
        for cap in range(1, d.units_total):
            r = self.invoke(pair(max_total_work=cap))
            self.assert_stopped(r, "INSUFFICIENT", "WORK_LIMIT")
            self.assertLessEqual(r.diagnostics.units_total, cap)
            seen.add(r.diagnostics.blocked_family)
        self.assertEqual(seen, set(primary + aux))
        self.assertEqual(r.diagnostics.last_stage, "publish.rows")
        budget = counter._Budget(CountLimits(), None)
        for amount in (-1, True):
            self.assertRaises(ValueError, budget.spend, "publish_visits", amount)
        self.assertEqual(budget.total, 0)

    def test_cancel_and_expire_before_and_after_final_row(self):
        req = pair()
        full = self.invoke(req)
        n = full.diagnostics.checkpoints
        for step, stage in ((2, "prepare"), (n-3, "publish.before"), (n-1, "publish.rows"),
                            (n, "publish.final")):
            for expire in (False, True):
                now = calls = 0
                def callback():
                    nonlocal now, calls
                    calls += 1
                    if calls == step:
                        now = 2_000_000_000
                        return not expire
                    return False
                with self.subTest(step=step, expire=expire), patch.object(counter, "perf_counter_ns", lambda: now):
                    r = self.invoke(req, cancelled=callback)
                    if expire:
                        self.assert_stopped(r, "INSUFFICIENT", "TIME_LIMIT")
                    else:
                        self.assert_stopped(r, "CANCELLED", "CANCELLED")
                    self.assertEqual(r.diagnostics.last_stage, stage)
                    if stage == "publish.final":
                        self.assertEqual(r.diagnostics.publish_visits, 2)
                        self.assertEqual(r.diagnostics.units_total, full.diagnostics.units_total)

    def test_contradictions_and_their_final_checkpoint(self):
        good = self.invoke(CountRequest([[1, -3, 1]], 1))
        self.assertEqual((good.status, good.base.total_worlds), ("COMPLETE", 1))
        for grid, mines in (([[0, -2, 1]], 1), ([[8]], 0), ([[1, -2]], 0), ([[0]], 1)):
            request = CountRequest(grid, mines)
            r = self.invoke(request)
            self.assertEqual((r.status, r.base.total_worlds, r.base.marginals),
                             ("INCONSISTENT_INPUT", 0, None))
            n = r.diagnostics.checkpoints
            for mode in ("error", "cancel", "time"):
                calls = now = 0
                def callback():
                    nonlocal calls, now
                    calls += 1
                    if calls == n:
                        now = 2_000_000_000
                        if mode == "error":
                            raise ValueError("contradiction publication")
                        return mode == "cancel"
                    return False
                with patch.object(counter, "perf_counter_ns", lambda: now):
                    stopped = self.invoke(request, cancelled=callback)
                self.assert_stopped(stopped, *{"error":("ERROR","CANCEL_CALLBACK_ERROR"),
                                               "cancel":("CANCELLED","CANCELLED"),
                                               "time":("INSUFFICIENT","TIME_LIMIT")}[mode])
                self.assertEqual(stopped.diagnostics.last_stage, "contradiction.final")

    def test_memo_size_skip_and_repeated_calls(self):
        full, repeat = self.invoke(pair()), self.invoke(pair())
        self.assertEqual(full.status, "COMPLETE")
        self.assertEqual(full.base, repeat.base)
        self.assertEqual(full.diagnostics.units_total, repeat.diagnostics.units_total)
        self.assertEqual(repeat.diagnostics.memo_lookups, full.diagnostics.memo_lookups)
        self.assertGreater(repeat.diagnostics.memo_hits, 0)
        memo = full.diagnostics.component_memo[0]
        # Leaf = free + one ways pair = 3. Root = free + one constraint pair
        # + one ways pair + two cells with one (k,count) pair each = 11.
        self.assertEqual((memo.entries_at_release, memo.scalars_at_release), (2, 14))
        self.assertEqual((full.diagnostics.memo_entries_peak, full.diagnostics.memo_scalars_peak), (2, 14))
        for limits in ({"memo_entries":1}, {"memo_scalars":13}, {"memo_scalars":1},
                       {"memo_entries":0}, {"memo_scalars":0}):
            r = self.invoke(pair(**limits))
            self.assertEqual(r.base, full.base)
            d = r.diagnostics
            if 0 in limits.values():
                self.assertEqual((d.memo_lookups,d.memo_stores,d.memo_operations,d.memo_entries_peak,
                                  d.memo_scalars_peak), (0,0,0,0,0))
            else:
                self.assertGreater(d.memo_skips, 0)
                self.assertLessEqual(d.memo_entries_peak, limits.get("memo_entries", 16384))
                self.assertLessEqual(d.memo_scalars_peak, limits.get("memo_scalars", 1000000))

    def test_components_floating_large_integers_and_no_closed_cells(self):
        req = CountRequest([[-2, 1, -2, -2, -2, -2, -2, 1, -3]], 3)
        r = self.invoke(req)
        self.assertEqual(r.diagnostics.component_sizes, (2, 2))
        self.assertEqual(r.diagnostics.floating_count, 3)
        self.assertEqual(r.base.total_worlds, 12)
        self.assertEqual([c.mine_worlds for c in r.base.marginals], [6,6,4,4,4,6,6])
        large = self.invoke(CountRequest([[-2]*100], 45))
        self.assertEqual(large.base.total_worlds, comb(100, 45))
        self.assertTrue(all(c.mine_worlds == comb(99, 44) for c in large.base.marginals))
        self.assertEqual(large.to_dict()["base"]["total_worlds"], str(comb(100, 45)))
        empty = self.invoke(CountRequest([[0, 0]], 0))
        self.assertEqual((empty.status, empty.base.total_worlds, empty.base.marginals), ("COMPLETE", 1, ()))

    def test_internal_error_is_atomic_and_charged(self):
        with patch.object(counter, "comb", side_effect=ArithmeticError("controlled fault")):
            r = self.invoke(CountRequest([[-2]*3], 1))
        self.assert_stopped(r, "ERROR", "INTERNAL_ERROR")
        self.assertGreater(r.diagnostics.units_total, 0)
        self.assertIn("controlled fault", r.diagnostics.error)
