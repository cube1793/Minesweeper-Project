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
        allowed = {"observation", "num_mines", "counted_inputs", "allow_guess", "prior_id", "limits"}
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


if __name__ == "__main__":
    unittest.main()

