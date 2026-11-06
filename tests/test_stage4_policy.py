from dataclasses import FrozenInstanceError, replace
from fractions import Fraction
import unittest
from unittest.mock import patch

import stage4_belief as belief
import stage4_candidates as candidates
import stage4_policy as policy
import stage4_posterior as posterior
import stage4_rollout as rollout
from stage4_candidates import CandidateLimits, EvidenceInput
from stage4_policy import ModelScore, PolicyLimits, PolicyRequest, RolloutPolicy, model_order
from stage4_rollout import RolloutBatch, RolloutRecord, VirtualBoard
from tests import stage4_policy_oracle as oracle


H, F = -2, -3
SHARED = ((1, H, 1), (H, H, H), (1, H, 1))
REPAIR = ((1, F, 1), (H, H, H), (1, H, 1))


def request(grid=((H, 1, H),), mines=1, c=1, **kwargs):
    return PolicyRequest(grid, mines, c, allow_guess=True, **kwargs)


def selected_row(result):
    return next(row for row in result.root.candidates if row.candidate_id == result.selected_candidate_id)


class PolicyTests(unittest.TestCase):
    def test_public_request_validation_and_immutability(self):
        base = {"observation": [[H, 1, H]], "num_mines": 1, "counted_inputs": 1}
        for key in ("engine", "mines", "board_seed", "bbbv", "active", "wasted", "snapshot"):
            with self.assertRaises(ValueError):
                PolicyRequest.from_payload({**base, key: None})
        with self.assertRaises((TypeError, ValueError)):
            PolicyRequest.from_payload({**base, "limits": {"unknown": 1}})
        parsed = PolicyRequest.from_payload({**base, "mode": "R", "target": {"numerator": "4", "denominator": "5"}})
        self.assertEqual(parsed.target, Fraction(4, 5))
        self.assertIsInstance(parsed.observation, tuple)
        with self.assertRaises((AttributeError, FrozenInstanceError)):
            parsed.mode = "M"
        for overrides in ({"target": 0}, {"counted_inputs": True}, {"planning_seed": object()}, {"allow_guess": 1}):
            with self.assertRaises((TypeError, ValueError)):
                PolicyRequest.from_payload({**base, **overrides})

    def test_synthetic_objective_matrix_and_exact_s_filter(self):
        a = (Fraction(3, 2),) * 3 + (Fraction(0),)
        b = (Fraction(9, 10),) * 4
        for target, expected in ((Fraction(1), "A"), (Fraction(4, 5), "B")):
            scores = {}
            for name, values in (("A", a), ("B", b)):
                mean, win, hit = oracle.matrix_summary(values, target)
                scores[name] = ModelScore(name, mean, win, hit, 4, 4)
            self.assertEqual(max(scores, key=lambda name: model_order(scores[name], 1, 0, "R")), expected)
            self.assertEqual(max(scores, key=lambda name: model_order(scores[name], 1, 0, "M")), "A")
            oracle.EMIT("synthetic_matrix", {"not_game_evidence": True, "target": target, "scores": scores})

        def matrix(grid, mines, c, guess, samples, shortlist, **kwargs):
            target = kwargs["target"]
            records = []
            for row in shortlist:
                values = b if row.pivot == (1, 0) else a if row.pivot == (2, 0) else (Fraction(0),) * 4
                for i, sample in enumerate(samples):
                    value = values[i]
                    outcome = "WON" if value else "LOST"
                    hit = value >= target and outcome == "WON" if target is not None else None
                    records.append(RolloutRecord(row.candidate_id, i, sample.rank, outcome, "SYNTHETIC",
                                                 value, hit, None, 0, (), ()))
            return RolloutBatch("COMPLETE", "SYNTHETIC_MATRIX", "PUBLIC_LOCAL_COST_P0_V1", tuple(records),
                                len(records), 0, 0, 0, 0.0, None)

        for mode, target, expected in (("S", None, (1, 0)), ("M", None, (2, 0)),
                                       ("R", Fraction(1), (2, 0)), ("R", Fraction(4, 5), (1, 0))):
            with patch.object(policy, "evaluate_rollouts", matrix):
                result = RolloutPolicy().select_next(request(((0, H, H, H, H, H),), 1, 1, mode=mode, target=target))
            self.assertEqual(result.status, "READY", result)
            self.assertEqual(selected_row(result).pivot, expected)
            self.assertEqual(result.selection_basis, "MODEL_SELECTED")
            if mode == "S":
                self.assertEqual(selected_row(result).survival_probability, 1)

    def test_all_modes_normal_model_selected_and_common_bank(self):
        results = [RolloutPolicy().select_next(request(mode=mode, target=Fraction(1) if mode == "R" else None,
                                                       planning_seed=77, episode_key="episode-" + mode))
                   for mode in ("S", "M", "R")]
        for result in results:
            self.assertEqual(result.status, "READY", result.reason)
            self.assertEqual(result.selection_basis, "MODEL_SELECTED")
            self.assertEqual(len(result.posterior.samples), 2)
            for score in result.scores:
                self.assertEqual(score.sample_count, 2)
                self.assertEqual(score.terminal_count, 2)
        self.assertEqual(results[0].posterior.samples, results[1].posterior.samples)
        self.assertEqual(results[1].posterior.samples, results[2].posterior.samples)
        self.assertEqual(results[2].target_status, "MODEL_ZERO_HITS")
        for result in results:
            bank = [sample.rank for sample in result.posterior.samples]
            for row in result.shortlist:
                if row.included:
                    ranks = [r.rank for r in result.rollouts.records if r.candidate_id == row.candidate_id]
                    self.assertEqual(ranks, bank)

    def test_all_modes_fallback_sampler_and_rollout_caps(self):
        for mode in ("S", "M", "R"):
            for limits in (PolicyLimits(sampler_work=0), PolicyLimits(rollouts=0)):
                result = RolloutPolicy().select_next(request(mode=mode, target=1 if mode == "R" else None, limits=limits))
                self.assertEqual(result.status, "READY", result.reason)
                self.assertEqual(result.selection_basis, "HEURISTIC_FALLBACK")
                self.assertTrue(all(score.rollout_mean_x is None for score in result.scores))
                if mode == "R":
                    self.assertEqual(result.target_status, "TARGET_NOT_EVALUATED")
        for limits in (PolicyLimits(virtual_inputs=0), PolicyLimits(pilot_work=0)):
            result = RolloutPolicy().select_next(request(((H, H, H, H, H),), 1, 0, limits=limits))
            self.assertEqual(result.selection_basis, "HEURISTIC_FALLBACK")

    def test_partial_matrix_cannot_choose_success_only_mean(self):
        complete = RolloutPolicy().select_next(request())
        batch = complete.rollouts
        rows = list(batch.records)
        rows[-1] = replace(rows[-1], outcome="NOT_STARTED", reason="INJECTED_CAP", value_x=None, hit=None)
        incomplete = replace(batch, status="INCOMPLETE", reason="INJECTED_CAP", records=tuple(rows))
        with patch.object(policy, "evaluate_rollouts", return_value=incomplete):
            result = RolloutPolicy().select_next(request())
        self.assertEqual(result.selection_basis, "HEURISTIC_FALLBACK")
        self.assertTrue(all(score.rollout_mean_x is None for score in result.scores))

    def test_target_required_root_guards_and_global_stop(self):
        missing = RolloutPolicy().select_next(request(mode="R"))
        self.assertEqual(missing.status, "TARGET_REQUIRED")
        self.assertIsNone(missing.action)
        for limits in (PolicyLimits(max_seconds=0), PolicyLimits(root=CandidateLimits(max_backend_calls=0))):
            result = RolloutPolicy().select_next(request(limits=limits))
            self.assertIsNone(result.action)
        for callback, status in ((lambda: True, "CANCELLED"), (lambda: None, "ERROR")):
            result = RolloutPolicy().select_next(request(), cancelled=callback)
            self.assertEqual(result.status, status)
            self.assertIsNone(result.action)
        blocked = RolloutPolicy().select_next(PolicyRequest(((H, 1, H),), 1, 1))
        self.assertEqual((blocked.status, blocked.reason), ("DEFER", "GUESS_DISABLED"))
        terminal = RolloutPolicy().select_next(PolicyRequest(((0,),), 0, 1))
        self.assertEqual(terminal.status, "PUBLIC_COMPLETE")
        inconsistent = RolloutPolicy().select_next(request(((2, H),), 1))
        self.assertEqual(inconsistent.status, "INCONSISTENT_INPUT")
        unsupported = RolloutPolicy().select_next(request(((H,),), 1))
        self.assertEqual(unsupported.status, "UNSUPPORTED")

    def test_backend_internal_cancel_and_time_before_and_after_exact_base(self):
        original = candidates.count_public
        for kind in ("cancel", "time"):
            for stop_call in (1, 2):
                state = {"entered": False, "calls": 0}

                def backend(query, **kwargs):
                    state["calls"] += 1
                    state["entered"] = state["calls"] >= stop_call
                    return original(query, **kwargs)

                callback = lambda: kind == "cancel" and state["entered"]
                clock = lambda: 31.0 if kind == "time" and state["entered"] else 0.0
                with patch.object(candidates, "count_public", backend), patch.object(policy, "perf_counter", clock):
                    result = RolloutPolicy().select_next(request(((H, H, H, H, H),), 1, 0), cancelled=callback)
                self.assertEqual(state["calls"], stop_call)
                self.assertEqual(result.status, "CANCELLED" if kind == "cancel" else "INSUFFICIENT")
                self.assertIsNone(result.action)
                self.assertIsNone(result.continuation)
                oracle.EMIT("backend_stop", {"kind": kind, "stop_call": stop_call, "result": result})

    def test_model_errors_do_not_fallback_and_final_cancel_wins(self):
        original = policy.sample_posterior

        def wrong_d(*args, **kwargs):
            value = original(*args, **kwargs)
            return replace(value, total_worlds=value.total_worlds + 1)

        with patch.object(policy, "sample_posterior", wrong_d):
            result = RolloutPolicy().select_next(request())
        self.assertEqual(result.status, "ERROR")
        self.assertIsNone(result.action)
        state = {"stop": False}
        actual = policy.evaluate_rollouts

        def finish_then_cancel(*args, **kwargs):
            result = actual(*args, **kwargs)
            state["stop"] = True
            return result

        with patch.object(policy, "evaluate_rollouts", finish_then_cancel):
            result = RolloutPolicy().select_next(request(), cancelled=lambda: state["stop"])
        self.assertEqual(result.status, "CANCELLED")
        self.assertIsNone(result.action)

    def test_flag_preparation_one_input_each_and_replan_after_reveal(self):
        board = VirtualBoard(REPAIR, 1, ((1, 1),))
        session = RolloutPolicy()
        current = request(REPAIR, 1, 5)
        actions = []
        for _ in range(8):
            result = session.select_next(current)
            self.assertEqual(result.status, "READY", result)
            actions.append(result.action)
            transition = board.step(result.action)
            self.assertTrue(transition.counted)
            if len(actions) <= 2:
                self.assertEqual(result.action.action, "FLAG")
                self.assertIsNotNone(result.continuation)
            if result.action.action in ("OPEN", "CHORD"):
                self.assertIsNone(result.continuation)
            if board.outcome is not None:
                break
            current = replace(current, observation=board.observation, counted_inputs=current.counted_inputs + 1,
                              continuation=result.continuation)
        self.assertEqual(board.outcome, "WON")
        self.assertEqual(len(set(actions[:2])), 2)
        self.assertEqual([a.action for a in actions[:3]], ["FLAG", "FLAG", "CHORD"])

    def test_continuation_stale_manual_settings_episode_duplicate_and_cancel(self):
        for change in ("manual", "mode", "target", "episode", "seed", "limits", "c", "duplicate", "missing", "forged", "cancel"):
            session = RolloutPolicy()
            initial = request(SHARED, 1, 4)
            first = session.select_next(initial)
            self.assertEqual(first.action.action, "FLAG")
            token = first.continuation
            follow = replace(initial, observation=token.expected_grid, counted_inputs=token.expected_c, continuation=token)
            callback = None
            if change == "manual":
                grid = [list(row) for row in follow.observation]
                grid[0][1] = F
                follow = replace(follow, observation=grid)
            elif change == "mode":
                follow = replace(follow, mode="M")
            elif change == "target":
                follow = replace(follow, target=Fraction(1))
            elif change == "episode":
                follow = replace(follow, episode_key="changed")
            elif change == "seed":
                follow = replace(follow, planning_seed=9)
            elif change == "limits":
                follow = replace(follow, limits=PolicyLimits(samples=8))
            elif change == "c":
                follow = replace(follow, counted_inputs=follow.counted_inputs + 1)
            elif change == "duplicate":
                accepted = session.select_next(follow)
                self.assertEqual(accepted.action.action, "CHORD")
            elif change == "missing":
                follow = replace(follow, continuation=None)
            elif change == "forged":
                follow = replace(follow, continuation=replace(token, serial=token.serial + 1))
            elif change == "cancel":
                callback = lambda: True
            result = session.select_next(follow, cancelled=callback)
            self.assertEqual(result.status, "CANCELLED" if change == "cancel" else "STALE", change)
            self.assertIsNone(result.action)
            self.assertIsNone(result.continuation)
        session = RolloutPolicy()
        initial = request(SHARED, 1, 4)
        first = session.select_next(initial)
        repeated = session.select_next(replace(initial, continuation=first.continuation))
        self.assertEqual(repeated.status, "STALE")

    def test_public_c_and_shortlist_exclusions(self):
        small = RolloutPolicy().select_next(request(c=1, limits=PolicyLimits(shortlist=1)))
        costly = RolloutPolicy().select_next(request(c=9, limits=PolicyLimits(shortlist=1)))
        self.assertEqual(sum(row.included for row in small.shortlist), 1)
        self.assertTrue(any(row.reason == "SHORTLIST_LIMIT" for row in small.shortlist))
        self.assertGreater(small.scores[0].rollout_mean_x, costly.scores[0].rollout_mean_x)

    def test_s_minimum_risk_includes_flagged_unknowns(self):
        result = RolloutPolicy().select_next(request(((H, 1, H, F, F, F, F, F),), 2, 6,
                                                     limits=PolicyLimits(sampler_work=0)))
        self.assertEqual(result.status, "READY")
        selected = selected_row(result)
        minimum = min(row.mine_worlds for row in result.root.base.marginals)
        count = next(row.mine_worlds for row in result.root.base.marginals if row.coordinate == selected.pivot)
        self.assertEqual(count, minimum)
        self.assertEqual(result.action.action, "FLAG")
        self.assertIn(selected.pivot[0], range(3, 8))

    def test_replacement_bank_multiplicity_reaches_every_candidate(self):
        class SameRankRandom:
            def __init__(self, seed):
                pass

            def randrange(self, stop):
                return 0

        with patch.object(posterior, "Random", SameRankRandom):
            result = RolloutPolicy().select_next(request(((H, H, H, H, H),), 1, 0,
                                                         limits=PolicyLimits(samples=2)))
        self.assertEqual(result.selection_basis, "MODEL_SELECTED")
        self.assertEqual(result.posterior.unique_layout_count, 1)
        for score in result.scores:
            self.assertEqual(score.sample_count, 2)
            group = [row for row in result.rollouts.records if row.candidate_id == score.candidate_id]
            self.assertEqual(len(group), 2)
            self.assertEqual(group[0].rank, group[1].rank)
            self.assertEqual(group[0].value_x, group[1].value_x)

    def test_unknown_model_status_and_bad_bank_are_errors(self):
        original = policy.sample_posterior
        for change in ("status", "seed", "count", "rank"):
            def corrupt(*args, **kwargs):
                value = original(*args, **kwargs)
                if change == "status":
                    return replace(value, status="UNRECOGNIZED")
                if change == "seed":
                    return replace(value, seed_id="wrong")
                if change == "count":
                    return replace(value, samples=value.samples[:1])
                return replace(value, samples=(replace(value.samples[0], rank=-1),) + value.samples[1:])

            with patch.object(policy, "sample_posterior", corrupt):
                result = RolloutPolicy().select_next(request())
            self.assertEqual(result.status, "ERROR", change)
            self.assertIsNone(result.action)
        with self.assertRaises(TypeError):
            PolicyRequest.from_payload({"observation": [[H,H]], "num_mines": 1, "counted_inputs": 0,
                                        "target": {"numerator": True, "denominator": 1}})

    def test_guess_off_pilot_unresolved_and_error_discard_pending(self):
        stalled = rollout.PilotResult("PILOT_UNRESOLVED", "INJECTED_LOCAL_STALL", (), 0, True, (), ())
        with patch.object(rollout, "pilot_p0", return_value=stalled):
            result = RolloutPolicy().select_next(PolicyRequest(SHARED, 1, 4))
        self.assertEqual(result.selection_basis, "HEURISTIC_FALLBACK")
        self.assertEqual(result.status, "READY")
        self.assertTrue(all(score.rollout_mean_x is None for score in result.scores))
        session = RolloutPolicy()
        initial = request(SHARED, 1, 4)
        first = session.select_next(initial)
        token = first.continuation
        follow = replace(initial, observation=token.expected_grid, counted_inputs=token.expected_c, continuation=token)
        error = session.select_next(follow, cancelled=lambda: "invalid")
        self.assertEqual(error.status, "ERROR")
        stale = session.select_next(follow)
        self.assertEqual(stale.status, "STALE")
        self.assertIsNone(stale.action)
