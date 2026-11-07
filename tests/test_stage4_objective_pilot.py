"""New G objective, complete-matrix and public-boundary tests."""

from dataclasses import fields, replace
from fractions import Fraction
import inspect
import json
import unittest
from unittest.mock import patch

import stage4_objective_pilot as g
from stage4_belief import exact_json
from stage4_candidates import EvidenceInput
from tests import stage4_pilot_oracle as oracle


H, F = -2, -3
G001 = ((H, 1, H), (H, H, F))
G009 = ((0, 1, F, H), (0, 1, H, 1))
G010 = ((H, 1, H), (H, H, H))


def request(grid=G001, mode="M", target=None, guess=True, **kwargs):
    return g.ObjectiveRequest(grid, 1, 2 if grid == G001 else 3 if grid == G009 else 1,
                              mode, guess, target, "unit8-tiny-common-bank", **kwargs)


class ObjectivePilotTests(unittest.TestCase):
    def test_safety_filter_and_risky_mr_candidates_with_safe_cell(self):
        replies = {mode: g.choose_objective(request(G009, mode, Fraction(1) if mode == "R" else None))
                   for mode in ("S", "M", "R")}
        for result in replies.values():
            self.assertEqual(result.status, "READY", result.reason)
            self.assertTrue(result.root.has_proven_safe_cell)
        for mode, result in replies.items():
            chosen = {entry.candidate_id for entry in result.shortlist if entry.included}
            probabilities = [candidate.survival_probability for candidate in result.root.candidates
                             if candidate.candidate_id in chosen]
            if mode == "S":
                self.assertTrue(all(value == 1 for value in probabilities))
            else:
                self.assertTrue(any(0 < value < 1 for value in probabilities))
        self.assertEqual(replies["S"].posterior.samples, replies["M"].posterior.samples)
        self.assertEqual(replies["M"].posterior.samples, replies["R"].posterior.samples)
        oracle.EMIT("objective_safety", {"results": replies})

    def test_model_rows_replay_independently_and_scores_are_exact_fractions(self):
        result = g.choose_objective(request())
        self.assertEqual(result.status, "READY", result.reason)
        for row in result.records:
            sample = result.posterior.samples[row.sample_index]
            replay = oracle.replay(G001, 1, sample.mines,
                                   [(move.action, move.x, move.y) for move in row.actions], 2)
            self.assertEqual(replay["outcome"], row.outcome)
            self.assertEqual(replay["X"], row.value_x)
            self.assertEqual(replay["added_inputs"], row.added_inputs)
        for score in result.scores:
            rows = [row for row in result.records if row.candidate_id == score.candidate_id]
            self.assertEqual(score.rollout_mean_x, sum((row.value_x for row in rows), Fraction()) / len(rows))
            self.assertEqual(score.rollout_win_rate, Fraction(sum(row.outcome == "WON" for row in rows), len(rows)))
            self.assertIsNone(score.rollout_hit_rate)
            self.assertEqual(score.pilot_id, g.Q_ID)
        self.assertEqual(result.expected_rows, len(result.records))
        self.assertEqual(result.followup_id, g.Q_ID)

    def test_r_target_is_primary_on_real_model_rows(self):
        for grid, target in ((G001, Fraction(1)), (G010, Fraction(6, 5))):
            query = request(grid, "R", target)
            result = g.choose_objective(query)
            self.assertEqual(result.status, "READY", result.reason)
            eligible, chosen, _ = g._shortlist(result.root, query)
            indices = {candidate.candidate_id: index for index, candidate in enumerate(eligible)}
            scores = {score.candidate_id: score for score in result.scores}
            expected = max(chosen, key=lambda candidate: g.model_order(
                scores[candidate.candidate_id], candidate.survival_probability,
                indices[candidate.candidate_id], "R"))
            self.assertEqual(result.selected_candidate_id, expected.candidate_id)
            for row in result.records:
                self.assertIs(row.hit, row.outcome == "WON" and row.value_x >= target)

    def test_exact_guess_blocked_is_zero_inside_q_model(self):
        result = g.choose_objective(request(G009, guess=False))
        self.assertEqual(result.status, "READY", result.reason)
        self.assertTrue(result.records)
        self.assertTrue(all(row.outcome == "GUESS_BLOCKED" for row in result.records))
        self.assertTrue(all(row.value_x == 0 for row in result.records))
        self.assertTrue(all(score.rollout_mean_x == 0 for score in result.scores))
        self.assertTrue(all(call.result.terminal_outcome == "GUESS_BLOCKED" for call in result.q_calls))

    def test_root_defer_no_viable_and_target_required(self):
        blocked = g.choose_objective(request(G010, guess=False))
        self.assertEqual((blocked.status, blocked.terminal_outcome), ("DEFER", "GUESS_BLOCKED"))
        all_mines = g.choose_objective(g.ObjectiveRequest(((H,),), 1, 0, "S", False))
        self.assertEqual((all_mines.status, all_mines.reason), ("DEFER", "NO_VIABLE_OPEN"))
        self.assertIsNone(all_mines.terminal_outcome)
        missing = g.choose_objective(request(mode="R"))
        self.assertEqual(missing.status, "TARGET_REQUIRED")
        self.assertFalse(missing.sequence)
        for target in (0, -1, 1.0, "1", Fraction(0)):
            with self.assertRaises((TypeError, ValueError)):
                request(mode="R", target=target)

    def test_incomplete_matrix_never_publishes_selection_or_scores(self):
        caps = [
            g.ObjectiveLimits(exact_work=0), g.ObjectiveLimits(local_work=0),
            g.ObjectiveLimits(max_seconds=0), g.ObjectiveLimits(samples=0),
            g.ObjectiveLimits(shortlist=0), g.ObjectiveLimits(rows=0),
            g.ObjectiveLimits(q_calls=0), g.ObjectiveLimits(virtual_inputs=0),
            g.ObjectiveLimits(inputs_per_rollout=0), g.ObjectiveLimits(backend_calls=0),
            g.ObjectiveLimits(sampler_work=0),
        ]
        for limits in caps:
            result = g.choose_objective(request(limits=limits))
            self.assertEqual(result.status, "INSUFFICIENT", (limits, result.reason))
            self.assertFalse(result.sequence)
            self.assertFalse(result.scores)
            self.assertIsNone(result.basis)
            self.assertIsNone(result.selected_candidate_id)
            self.assertTrue(all(row.value_x is None for row in result.records
                                if row.outcome not in ("WON", "LOST", "GUESS_BLOCKED")))
            self.assertLessEqual(result.usage.exact_work, limits.exact_work)
            self.assertLessEqual(result.usage.local_work, limits.local_work)

    def test_cancellation_and_callback_error(self):
        for callback, expected in ((lambda: True, "CANCELLED"), (lambda: 1, "ERROR")):
            result = g.choose_objective(request(), cancelled=callback)
            self.assertEqual(result.status, expected)
            self.assertFalse(result.sequence)
            self.assertFalse(result.scores)

    def test_invalid_posterior_binding_is_error(self):
        original = g.sample_posterior
        def changed(query, **kwargs):
            return replace(original(query, **kwargs), seed_id="wrong-public-binding")
        with patch.object(g, "sample_posterior", changed):
            result = g.choose_objective(request())
        self.assertEqual(result.status, "ERROR")
        self.assertFalse(result.sequence)
        self.assertFalse(result.scores)

    def test_recursive_g_is_rejected_during_model_setup(self):
        original = g.sample_posterior
        nested = []
        def probe(query, **kwargs):
            nested.append(g.choose_objective(request()))
            return original(query, **kwargs)
        with patch.object(g, "sample_posterior", probe):
            result = g.choose_objective(request())
        self.assertEqual(result.status, "READY")
        self.assertEqual(len(nested), 1)
        self.assertEqual((nested[0].status, nested[0].reason), ("ERROR", "RECURSIVE_G_FORBIDDEN"))
        self.assertFalse(nested[0].sequence)

    def test_q_receives_only_registered_public_fields(self):
        result = g.choose_objective(request())
        self.assertTrue(result.q_calls)
        allowed = {"observation", "num_mines", "counted_inputs", "allow_guess", "prior_id", "limits",
                   "base_backend"}
        for call in result.q_calls:
            self.assertEqual({field.name for field in fields(call.request)}, allowed)
            self.assertEqual(call.request.allow_guess, True)
            self.assertEqual(call.result.pilot_id, g.Q_ID)
            self.assertLessEqual(call.request.limits.max_seconds, 2.0)
        self.assertEqual(tuple(inspect.signature(g.choose_objective).parameters), ("request", "cancelled"))

    def test_payload_roundtrip_preserves_numeric_types_and_seed_kind(self):
        identities = set()
        for seconds in (30, 30.0):
            for seed in (7, "7"):
                query = replace(request(mode="R", target=Fraction(6, 5)),
                                planning_seed=seed, limits=g.ObjectiveLimits(max_seconds=seconds))
                restored = g.ObjectiveRequest.from_payload(json.loads(json.dumps(query.to_payload())))
                self.assertEqual(restored, query)
                self.assertIs(type(restored.planning_seed), type(seed))
                self.assertIs(type(restored.limits.max_seconds), type(seconds))
                self.assertEqual(restored.identity, query.identity)
                identities.add(query.identity)
        self.assertEqual(len(identities), 4)

    def test_hidden_fields_rejected_and_public_world_independence(self):
        for forbidden in ("mines", "virtual_b", "rank", "actual_seed", "active", "engine", "episode_key"):
            payload = request().to_payload()
            payload[forbidden] = 1
            with self.assertRaises((TypeError, ValueError)):
                g.ObjectiveRequest.from_payload(payload)
        worlds = [oracle.World(G001, 1, positions) for positions in (((0, 0),), ((2, 1),))]
        results = [g.choose_objective(replace(request(), observation=world.observation)) for world in worlds]
        self.assertEqual(results[0].request_id, results[1].request_id)
        self.assertEqual(results[0].sequence, results[1].sequence)
        self.assertEqual(results[0].scores, results[1].scores)
        self.assertEqual(results[0].posterior.samples, results[1].posterior.samples)
        self.assertEqual(results[0].usage.cache_hits, results[1].usage.cache_hits)

    def test_chord_joint_survival_and_flag_cost_against_oracle(self):
        grid = ((F, H, H), (H, 1, H), (H, H, H))
        query = g.ObjectiveRequest(grid, 1, 2, "M", True)
        result = g.choose_objective(query)
        self.assertEqual(result.status, "READY")
        expected = oracle.posterior(grid, 1)
        existing = next(candidate for candidate in result.root.candidates
                        if candidate.sequence == (EvidenceInput("CHORD", 1, 1),))
        self.assertEqual(existing.survival_probability, Fraction(1, 8))
        self.assertNotEqual(existing.survival_probability, Fraction(7, 8)**7)
        for candidate in result.root.candidates:
            worlds = oracle.event_worlds(expected["layouts"], candidate.targets)
            self.assertEqual(worlds, candidate.survival.worlds)
            self.assertEqual(candidate.immediate_input_cost, len(candidate.sequence))
        flagged = next(candidate for candidate in result.root.candidates
                       if candidate.kind == "OPEN" and candidate.pivot == (0, 0))
        self.assertEqual(flagged.immediate_input_cost, 2)

    def test_oracle_source_is_independent(self):
        source = inspect.getsource(oracle)
        self.assertNotIn("from stage4", source)
        self.assertNotIn("import stage4", source)
        self.assertNotIn("core_engine", source)
        self.assertNotIn("VirtualBoard", source)


class SummedObjectivePilotTests(unittest.TestCase):
    def query(self, **kwargs):
        return request(base_backend=g.UNIT10_SUMMED, **kwargs)

    def assert_join(self, result):
        calls = result.q_calls
        for name in ("counter_units_total", "counter_primary_work", "counter_auxiliary_work",
                     "counter_backend_calls", "local_work"):
            self.assertEqual(getattr(result.usage, name), sum(getattr(c.result, name) for c in calls))
        self.assertEqual(result.usage.exact_work, result.usage.backend_work + result.usage.sampler_work)
        balance = None
        for call in calls:
            settlement = call.counter_settlement
            if balance is not None:
                self.assertEqual(settlement.balance_before, balance)
            self.assertEqual(settlement.lease_units, call.request.limits.counter_units)
            self.assertEqual(settlement.units_total, call.result.counter_units_total)
            balance = settlement.balance_after
            self.assertEqual(balance, settlement.balance_before - settlement.units_total)
            self.assertLessEqual(call.request.limits.counter_units, 200000)
            self.assertLessEqual(call.request.limits.max_seconds, 2.0)

    def test_complete_model_preserves_legacy_meaning_and_separate_accounts(self):
        for grid, mode, target in ((G001, "M", None), (G010, "R", Fraction(6, 5))):
            old = g.choose_objective(request(grid, mode, target))
            new = g.choose_objective(request(grid, mode, target, base_backend=g.UNIT10_SUMMED))
            self.assertEqual((new.status, new.sequence, new.selected_candidate_id),
                             (old.status, old.sequence, old.selected_candidate_id))
            self.assertEqual(new.status, "READY")
            self.assertEqual(new.posterior.samples, old.posterior.samples)
            self.assertEqual(new.shortlist, old.shortlist)
            self.assertEqual(new.records, old.records)
            self.assertEqual([(s.rollout_mean_x, s.rollout_win_rate, s.rollout_hit_rate) for s in new.scores],
                             [(s.rollout_mean_x, s.rollout_win_rate, s.rollout_hit_rate) for s in old.scores])
            self.assertNotEqual(new.pilot_id, old.pilot_id)
            self.assertNotEqual(new.followup_id, old.followup_id)
            self.assertTrue(all(s.pilot_id == new.followup_id for s in new.scores))
            self.assertEqual(old.usage.counter_units_total, 0)
            self.assertGreater(new.usage.counter_units_total, 0)
            self.assertTrue(new.usage.work_accounting_complete)
            self.assert_join(new)

    def test_g_dto_precheck_and_typed_roundtrip(self):
        self.assertEqual(fields(g.ObjectiveRequest)[-1].name, "base_backend")
        self.assertEqual(fields(g.ObjectiveLimits)[-1].name, "counter_units")
        grid480 = ((H,) * 30,) * 16
        self.assertEqual(len(g.ObjectiveRequest(grid480, 99, 0, "M", True,
                                               base_backend=g.UNIT10_SUMMED).observation), 16)
        oversized = ((object(),) * 481,)
        with self.assertRaisesRegex(ValueError, "CELL_LIMIT_BEFORE_ID"):
            g.ObjectiveRequest(oversized, 1, 0, "M", True, base_backend=g.UNIT10_SUMMED)
        payload = self.query().to_payload()
        payload["observation"] = oversized
        with patch.object(g, "_grid_payload", side_effect=AssertionError("decoded before size guard")):
            with self.assertRaisesRegex(ValueError, "CELL_LIMIT_BEFORE_ID"):
                g.ObjectiveRequest.from_payload(payload)
        legacy = g.choose_objective(g.ObjectiveRequest(((H,) * 481,), 1, 0, "M", True))
        self.assertEqual((legacy.status, legacy.reason), ("UNSUPPORTED", "CELL_LIMIT"))
        for value in (True, -1, 60000001, 1.0):
            with self.assertRaises(ValueError):
                g.ObjectiveLimits(counter_units=value)
        ids = set()
        for seconds in (30, 30.0):
            for seed in (7, "7"):
                original = replace(self.query(), planning_seed=seed,
                                   limits=g.ObjectiveLimits(max_seconds=seconds))
                restored = g.ObjectiveRequest.from_payload(json.loads(json.dumps(original.to_payload())))
                self.assertEqual(original, restored)
                self.assertIs(type(restored.limits.max_seconds), type(seconds))
                self.assertIs(type(restored.planning_seed), type(seed))
                self.assertEqual(original.identity, restored.identity)
                ids.add(original.identity)
        self.assertEqual(len(ids), 4)
        for name in ("active", "wasted", "actual_layout", "progress_bbbv"):
            payload = self.query().to_payload()
            payload[name] = 0
            with self.assertRaises(ValueError):
                g.ObjectiveRequest.from_payload(payload)

    def test_zero_counter_precedes_root_and_small_parent_lease_stops(self):
        with patch.object(g, "analyze_candidates", side_effect=AssertionError("zero must precede root")):
            zero = g.choose_objective(self.query(limits=g.ObjectiveLimits(counter_units=0)))
        self.assertEqual((zero.status, zero.reason), ("INSUFFICIENT", "ZERO_COUNTER_WORK_LIMIT"))
        self.assertEqual(zero.usage.counter_units_total, 0)
        self.assertFalse(zero.records)
        small = g.choose_objective(self.query(limits=g.ObjectiveLimits(counter_units=1)))
        self.assertEqual(small.status, "INSUFFICIENT")
        self.assertFalse(small.sequence)
        self.assertFalse(small.scores)
        self.assert_join(small)
        self.assertEqual(sum(c.result.counter_backend_calls for c in small.q_calls), 1)
        self.assertEqual(small.q_calls[-1].request.limits.counter_units, 1)
        self.assertLessEqual(small.usage.counter_units_total, 1)

    def test_exact_lease_settles_once_and_rejects_exhausted_parent(self):
        import stage4_exact_pilot as q
        for cap in (114, 115):
            parent = self.query(limits=g.ObjectiveLimits(counter_units=cap))
            budget = g._Budget(parent, None)
            child = q.ExactRequest(((H, 1, H),), 1, 2, True,
                                   limits=q.ExactLimits(counter_units=cap), base_backend=q.UNIT10_SUMMED)
            budget.reserve_q(child)
            result = q.choose_exact(child)
            budget.settle_q(child, result)
            self.assertEqual(budget.counter_units_total, result.counter_units_total)
            self.assertEqual(budget.counter_settlement.balance_after, cap - result.counter_units_total)
            with self.assertRaisesRegex(ValueError, "already settled"):
                budget.settle_q(child, result)
            self.assertEqual(budget.counter_units_total, result.counter_units_total)
            if cap == 115:
                with self.assertRaises(g._Stop):
                    budget.require(budget.counter_units_total, cap, "COUNTER_WORK_LIMIT")

    def test_parent_cancel_callback_error_and_time_keep_child_q_g_spend(self):
        import stage4_exact_pilot as q
        real = q.count_base
        for kind, status in (("cancel", "CANCELLED"), ("callback", "ERROR"), ("time", "INSUFFICIENT")):
            returned = [False]
            def counted(child, **kwargs):
                raw = real(child, **kwargs)
                returned[0] = True
                return raw
            def callback():
                return (1 if kind == "callback" else kind == "cancel") if returned[0] else False
            with patch.object(q, "count_base", counted), patch.object(g, "perf_counter",
                    lambda: 31.0 if kind == "time" and returned[0] else 0.0):
                result = g.choose_objective(self.query(), cancelled=callback)
            self.assertEqual(result.status, status)
            self.assertGreater(result.usage.counter_units_total, 0)
            self.assertTrue(result.usage.work_accounting_complete)
            self.assert_join(result)
            self.assertFalse(result.sequence)
            self.assertFalse(result.scores)
            self.assertEqual(sum(c.result.counter_backend_calls for c in result.q_calls), 1)

    def test_bounded_count_internal_error_propagates_and_stops_remaining_rows(self):
        import stage4_belief_counter as counter
        with patch.object(counter, "_weighted", side_effect=RecursionError("bounded injection only")):
            result = g.choose_objective(self.query())
        self.assertEqual((result.status, result.reason), ("ERROR", "Q_BASE_INTERNAL_ERROR"))
        self.assertGreater(result.usage.counter_units_total, 0)
        self.assertTrue(result.usage.work_accounting_complete)
        self.assert_join(result)
        self.assertEqual(sum(c.result.counter_backend_calls for c in result.q_calls), 1)
        self.assertEqual(result.q_calls[-1].result.status, "ERROR")
        self.assertFalse(result.sequence)
        self.assertFalse(result.scores)
        self.assertTrue(any(r.outcome == "NOT_STARTED" for r in result.records))
        self.assertTrue(all(r.value_x is None for r in result.records if r.outcome in ("UNRESOLVED", "NOT_STARTED")))

    def test_unknown_q_spend_stops_and_bad_identity_preserves_valid_charge(self):
        import stage4_exact_pilot as q
        real = q.ExactPilot.choose
        for kind in ("type", "bool", "negative", "sum", "exception", "identity", "version"):
            def changed(pilot, child, **kwargs):
                result = real(pilot, child, **kwargs)
                if not result.counter_backend_calls:
                    return result
                if kind == "type":
                    return None
                if kind == "exception":
                    raise RuntimeError("Q response lost after work")
                if kind == "bool":
                    return replace(result, counter_units_total=True)
                if kind == "negative":
                    return replace(result, counter_primary_work=-1)
                if kind == "sum":
                    return replace(result, counter_units_total=result.counter_units_total + 1)
                return replace(result, **{("request_id" if kind == "identity" else "counter_work_accounting_version"): "bad"})
            with patch.object(q.ExactPilot, "choose", changed):
                result = g.choose_objective(self.query())
            self.assertEqual(result.status, "ERROR")
            self.assertFalse(result.sequence)
            self.assertFalse(result.scores)
            if kind in ("identity", "version"):
                self.assertTrue(result.usage.work_accounting_complete)
                self.assertGreater(result.usage.counter_units_total, 0)
                self.assert_join(result)
            else:
                self.assertFalse(result.usage.work_accounting_complete)
                self.assertEqual(result.q_calls[-1].counter_settlement.status, "UNKNOWN_SPEND")

    def test_new_backend_guess_off_public_equivalence_and_cache_finally_clear(self):
        import stage4_exact_pilot as q
        pilots = []
        def factory(capacity):
            pilot = q.ExactPilot(capacity)
            pilots.append(pilot)
            return pilot
        with patch.object(g, "ExactPilot", factory):
            result = g.choose_objective(request(G009, guess=False, base_backend=g.UNIT10_SUMMED))
        self.assertEqual(result.status, "READY")
        self.assertTrue(all(row.outcome == "GUESS_BLOCKED" and row.value_x == 0 for row in result.records))
        self.assertEqual(len(pilots), 1)
        self.assertFalse(pilots[0]._cache)
        worlds = [oracle.World(G001, 1, positions) for positions in (((0, 0),), ((2, 1),))]
        replies = [g.choose_objective(replace(self.query(), observation=w.observation)) for w in worlds]
        self.assertEqual(replies[0].request_id, replies[1].request_id)
        self.assertEqual(replies[0].sequence, replies[1].sequence)
        self.assertEqual(replies[0].scores, replies[1].scores)
        self.assertEqual(replies[0].posterior.samples, replies[1].posterior.samples)


if __name__ == "__main__":
    unittest.main()

