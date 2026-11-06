"""Focused Unit 3 evaluator tests. Fake policy results are confined here."""

from dataclasses import replace
from fractions import Fraction
import json
from time import monotonic
import unittest
from unittest.mock import patch

import stage4_evaluation as evaluation
import stage4_planning as planning


H, F = -2, -3


def two_ends():
    return evaluation.prepare_case(evaluation.PublicCase(
        ((H, 1, H),), 1, (planning.Move("OPEN", 1, 0),)))


def settings(guess=True):
    return evaluation.Settings("M", guess, Fraction(1))


def fake_result(request, action=None, status="OK", reason=None, score=None):
    result = {"identity": request.identity, "observation_id": request.observation_id,
              "status": status, "reason": reason, "action": None,
              "score": None, "terminal_outcome": None, "exactness": None,
              "trace": {"untrusted_partial": {"selected": {"action": "OPEN", "x": "0", "y": "0"}}}}
    if status in ("OK", "DEFER"):
        result.update(action=planning.exact_json(action), exactness=evaluation.EXACT,
                      score=(score or planning.Score(win_probability=Fraction(1))).to_dict())
    if status == "DEFER":
        result.update(terminal_outcome="GUESS_BLOCKED", reason="GUESS_DISABLED",
                      score=planning.Score(blocked_probability=Fraction(1)).to_dict())
    return result


class EvaluationTests(unittest.TestCase):
    def test_public_boundary_and_nested_payload_allowlist(self):
        case = two_ends()
        request = evaluation.request_for(case, settings())
        self.assertEqual(set(planning.exact_json(request)), evaluation.PUBLIC_FIELDS)
        self.assertEqual(set(planning.exact_json(request.ledger[0])), evaluation.LEDGER_FIELDS)
        for forbidden in ("engine", "layout", "seed", "bbbv", "active", "wasted", "attempt_id"):
            with self.subTest(forbidden=forbidden), self.assertRaises((TypeError, ValueError)):
                evaluation.public_request(observation=((H, 1, H),), num_mines=1,
                    ledger=case.ledger, mode="S", allow_guess=True, target="1",
                    limits=planning.Limits(), **{forbidden: 1})
            with self.assertRaises(ValueError):
                planning.PlanningRequest.from_payload({"observation": ((H,),), "num_mines": 0, forbidden: 1})
        with self.assertRaises(TypeError):
            planning.PlanningRequest.from_payload({"observation": ((H,),), "num_mines": 0,
                "ledger": [{"action": "FLAG", "x": 0, "y": 0, "counted": True,
                            "observation_id": "0" * 64, "active": 1}]})

    def test_public_identity_ignores_private_layout_and_counter_split(self):
        case = evaluation.prepare_case(evaluation.PublicCase(
            ((F, 1, H, H, H),), 1,
            (planning.Move("OPEN", 1, 0), planning.Move("FLAG", 0, 0))))
        self.assertEqual(case.status, "VALID")
        counters = [row["transitions"][-1]["private_counters"] for row in case.replay_records]
        self.assertNotEqual(counters[0]["active_clicks"], counters[1]["active_clicks"])
        trials = evaluation.plan_trials(case, settings())
        self.assertEqual(len({trial.request_id for trial in trials}), 1)
        self.assertNotIn("private_counters", json.dumps(planning.exact_json(evaluation.request_for(case, settings()))))

    def test_prefix_replays_every_layout_and_binds_each_observation(self):
        case = two_ends()
        self.assertEqual(case.status, "VALID")
        self.assertEqual(len(case.layouts), 2)
        self.assertTrue(all(row["matches"] for row in case.replay_records))
        self.assertEqual(case.public.transcript, (((H, 1, H),),))
        self.assertEqual(sum(item.counted for item in case.ledger), 1)

    def test_unreachable_prefix_and_inconsistent_case_are_rejected(self):
        unreachable = evaluation.prepare_case(evaluation.PublicCase(
            ((H, 0, H),), 0, (planning.Move("OPEN", 1, 0),)))
        self.assertEqual(unreachable.status, "PREFIX_NOT_REPLAYABLE")
        with self.assertRaises(ValueError):
            evaluation.plan_trials(unreachable, settings())
        inconsistent = evaluation.prepare_case(evaluation.PublicCase(((H, 3, H),), 1))
        self.assertEqual(inconsistent.status, "INCONSISTENT_INPUT")

    def test_posterior_subset_is_not_silently_renormalized(self):
        original = evaluation._replay
        def changed_transcript(case, mines):
            answer = original(case, mines)
            if mines == ((2, 0),):
                return (*answer[:3], (), False)
            return answer
        with patch.object(evaluation, "_replay", side_effect=changed_transcript):
            case = two_ends()
        self.assertEqual(case.status, "POSTERIOR_MISMATCH")
        self.assertEqual(len(case.layouts), 2)
        with self.assertRaises(ValueError):
            evaluation.plan_trials(case, settings())

    def test_flag_is_one_input_then_fresh_request_even_with_a_partial_route(self):
        case = two_ends()
        trial = evaluation.plan_trials(case, settings())[0]
        seen = []
        def fake(request):
            seen.append(request)
            if len(seen) == 1:
                return fake_result(request, planning.Move("FLAG", 2, 0))
            return fake_result(request, status="INSUFFICIENT", reason="RESOURCE_LIMIT")
        with patch.object(planning, "plan_next", side_effect=fake):
            result = evaluation.run_attempt(case, trial, evaluation.Budget(4))
        self.assertEqual(result.outcome, "UNRESOLVED")
        self.assertEqual(result.additional_inputs, 1)
        self.assertEqual([r.total_c for r in seen], [1, 2])
        self.assertEqual(seen[1].observation, ((H, 1, F),))
        self.assertNotEqual(seen[0].identity, seen[1].identity)
        self.assertEqual(sum(e["event"] == "input_end" for e in result.events), 1)
        self.assertEqual(result.events[-1]["event"], "attempt_end")

    def test_incomplete_statuses_never_execute_partial_selected_action(self):
        case = two_ends()
        trial = evaluation.plan_trials(case, settings())[0]
        for status in ("INSUFFICIENT", "TARGET_REQUIRED", "INCONSISTENT_INPUT", "ERROR"):
            with self.subTest(status=status), patch.object(planning, "plan_next",
                    side_effect=lambda request: fake_result(request, status=status, reason=status)):
                result = evaluation.run_attempt(case, trial, evaluation.Budget(4))
            self.assertEqual(result.outcome, "UNRESOLVED")
            self.assertIsNone(result.x)
            self.assertEqual(result.additional_inputs, 0)
            self.assertEqual(len(result.calls), 1)

    def test_malformed_or_stale_response_has_zero_engine_inputs(self):
        case = two_ends()
        trial = evaluation.plan_trials(case, settings())[0]
        for corruption in ("multiple", "stale", "incomplete_action", "outside"):
            def fake(request):
                result = fake_result(request, planning.Move("OPEN", 2, 0))
                if corruption == "multiple":
                    result["action"] = [result["action"], result["action"]]
                elif corruption == "stale":
                    result["identity"] = "0" * 64
                elif corruption == "outside":
                    result["action"]["x"] = "99"
                else:
                    result["status"] = "INSUFFICIENT"
                return result
            with self.subTest(corruption=corruption), patch.object(planning, "plan_next", side_effect=fake):
                result = evaluation.run_attempt(case, trial, evaluation.Budget(4))
            self.assertEqual(result.reason, "POLICY_PROTOCOL_ERROR")
            self.assertEqual(result.additional_inputs, 0)

    def test_four_outcomes_and_not_started_have_distinct_utility(self):
        case = two_ends()
        trial = evaluation.plan_trials(case, settings())[0]
        for move, expected in ((planning.Move("OPEN", 0, 0), "LOST"),
                               (planning.Move("OPEN", 2, 0), "WON")):
            with patch.object(planning, "plan_next", side_effect=lambda request: fake_result(request, move)):
                answer = evaluation.run_attempt(case, trial, evaluation.Budget(4))
            self.assertEqual(answer.outcome, expected)
            self.assertEqual(len(answer.calls), 1)
            self.assertEqual(answer.additional_inputs, 1)
            self.assertEqual(answer.x, Fraction(0) if expected == "LOST" else Fraction(1, 2))
        blocked_trial = evaluation.plan_trials(case, settings(False))[0]
        with patch.object(planning, "plan_next", side_effect=lambda request: fake_result(request, status="DEFER")):
            blocked = evaluation.run_attempt(case, blocked_trial, evaluation.Budget(4))
        self.assertEqual((blocked.outcome, blocked.x), ("GUESS_BLOCKED", 0))
        unstarted = evaluation.run_attempt(case, trial, evaluation.Budget(0))
        self.assertEqual(unstarted.execution_state, "NOT_STARTED")
        self.assertIsNone(unstarted.outcome)
        self.assertIsNone(unstarted.x)

    def test_budget_stops_preserve_previous_ok_and_apply_no_later_inputs(self):
        case = two_ends()
        trial = evaluation.plan_trials(case, settings())[0]
        with patch.object(planning, "plan_next", side_effect=lambda request: fake_result(request, planning.Move("FLAG", 0, 0))):
            answer = evaluation.run_attempt(case, trial, evaluation.Budget(10, max_inputs=1))
        self.assertEqual((answer.outcome, answer.reason), ("UNRESOLVED", "INPUT_BUDGET"))
        self.assertEqual(answer.calls[0]["status"], "OK")
        self.assertEqual(answer.additional_inputs, 1)
        expired = evaluation.run_attempt(case, trial, evaluation.Budget(10, deadline=monotonic()-1))
        self.assertEqual((expired.execution_state, expired.reason), ("NOT_STARTED", "BATCH_DEADLINE"))

    def test_planner_exception_is_unresolved_and_journaled(self):
        case = two_ends()
        with patch.object(planning, "plan_next", side_effect=RuntimeError("unit-test-only")):
            answer = evaluation.run_attempt(case, evaluation.plan_trials(case, settings())[0], evaluation.Budget(2))
        self.assertEqual((answer.outcome, answer.reason), ("UNRESOLVED", "PLANNER_EXCEPTION"))
        self.assertTrue(any(e["event"] == "call_error" for e in answer.events))
        self.assertEqual(answer.additional_inputs, 0)

    def test_aggregate_rejects_missing_duplicate_and_weight_mismatch(self):
        case = two_ends()
        trials = evaluation.plan_trials(case, settings())
        attempts = tuple(evaluation.run_attempt(case, trial, evaluation.Budget(0)) for trial in trials)
        for broken in (attempts[:1], attempts + attempts[:1]):
            with self.assertRaises(ValueError):
                evaluation.aggregate(trials, broken)
        altered = (replace(trials[0], weight=Fraction(1, 3)), trials[1])
        with self.assertRaises(ValueError):
            evaluation.aggregate(altered, tuple(replace(a, trial=t) for a, t in zip(attempts, altered)))
        with self.assertRaises(ValueError):
            evaluation.aggregate(trials, (replace(attempts[0], total_c=9), attempts[1]))

    def test_unknown_mass_keeps_full_denominator_and_exact_bounds(self):
        case = two_ends()
        trials = evaluation.plan_trials(case, settings())
        known = evaluation.Attempt(trials[0], "COMPLETED", "WON", "fixture", 2, 1)
        missing = evaluation.run_attempt(case, trials[1], evaluation.Budget(0))
        summary = evaluation.aggregate(trials, (known, missing))
        self.assertIsNone(summary["complete_mean"])
        self.assertEqual(summary["coverage"], Fraction(1, 2))
        self.assertEqual(summary["intervals"]["expected_x"], {"lower": Fraction(1, 4), "upper": Fraction(3, 4)})
        self.assertEqual(summary["counts"]["not_started"], 1)
        self.assertEqual(summary["comparison"], "INSUFFICIENT")

    def test_large_integer_and_rational_serialization_is_lossless(self):
        value = Fraction(10**80 + 1, 10**70 + 3)
        encoded = planning.exact_json({"large": 10**90, "value": value})
        restored = json.loads(json.dumps(encoded))
        self.assertEqual(restored["large"], str(10**90))
        self.assertEqual(evaluation.read_fraction(restored["value"]), value)
        with self.assertRaises(ValueError):
            evaluation.read_fraction({"numerator": 1.0, "denominator": "2"})

    def test_primary_comparison_and_secondary_differences_are_separate(self):
        case = two_ends()
        trials = evaluation.plan_trials(case, replace(settings(), target=Fraction(1, 2)))
        for initial_x, expected in ((Fraction(1, 2), "MATCH"), (Fraction(1, 4), "STRICTLY_HIGHER"),
                                    (Fraction(3, 4), "CONTRADICTION")):
            score = planning.Score(initial_x, Fraction(1), Fraction(0)).to_dict()
            attempts = tuple(evaluation.Attempt(t, "COMPLETED", "WON", "synthetic_aggregation_test",
                2, 1, ({"score": score},), True) for t in trials)
            summary = evaluation.aggregate(trials, attempts)
            self.assertEqual(summary["comparison"], expected)
            self.assertEqual(summary["component_deltas"]["target_probability"], 1)

    def test_real_planner_through_normal_entry_point(self):
        case = two_ends()
        for guess in (True, False):
            trials = evaluation.plan_trials(case, settings(guess))
            budget = evaluation.Budget(10)
            attempts = tuple(evaluation.run_attempt(case, trial, budget) for trial in trials)
            summary = evaluation.aggregate(trials, attempts)
            self.assertEqual(summary["comparison"], "MATCH")
            self.assertEqual(summary["counts"]["GUESS_BLOCKED"], 0 if guess else 2)
            self.assertEqual(summary["counts"]["LOST"], 1 if guess else 0)
            self.assertEqual(summary["complete_mean"]["expected_x"], Fraction(1, 4) if guess else 0)

    def test_real_shared_flag_replans_after_each_atomic_input(self):
        case = evaluation.prepare_case(evaluation.PublicCase(
            ((1, H, 1), (H, H, H), (1, H, 1)), 1,
            tuple(planning.Move("OPEN", x, y) for x, y in ((0, 0), (2, 0), (0, 2), (2, 2)))))
        trial = evaluation.plan_trials(case, settings())[0]
        answer = evaluation.run_attempt(case, trial, evaluation.Budget(10))
        self.assertEqual(answer.outcome, "WON")
        self.assertEqual(answer.x, Fraction(8, 7))
        self.assertEqual(answer.additional_inputs, 3)
        self.assertEqual(answer.calls[0]["action"]["action"], "FLAG")
        self.assertEqual(len(answer.calls), answer.additional_inputs)


if __name__ == "__main__":
    unittest.main()
