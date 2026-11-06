from dataclasses import replace
from fractions import Fraction
import inspect
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from core_engine import Action, GameStatus, MinesweeperEngine
from stage4_candidates import EvidenceInput
from stage4_posterior import PosteriorSample
import stage4_rollout as rollout
from stage4_rollout import VirtualBoard, RolloutLimits, evaluate_rollouts, pilot_p0
from tests import stage4_policy_oracle as oracle


H, F = -2, -3


def candidate(*actions):
    return SimpleNamespace(candidate_id="fixture", sequence=tuple(EvidenceInput(*a) for a in actions))


class RolloutTests(unittest.TestCase):
    def test_virtual_transitions_bbbv_and_c_match_fixed_engine(self):
        fixtures = [
            (5, 1, ((2, 0),), (("FLAG", 1, 0), ("OPEN", 0, 0), ("OPEN", 4, 0), ("OPEN", 2, 0))),
            (3, 2, ((0, 0), (2, 0)), (("OPEN", 1, 1), ("FLAG", 0, 1), ("FLAG", 2, 1), ("CHORD", 1, 1))),
            (6, 1, ((2, 0), (5, 0)), (("OPEN", 0, 0), ("CHORD", 0, 0), ("FLAG", 3, 0),
                                      ("OPEN", 3, 0), ("FLAG", 3, 0), ("OPEN", 3, 0), ("OPEN", 4, 0))),
        ]
        for index, (width, height, mines, actions) in enumerate(fixtures):
            engine = MinesweeperEngine(width, height, len(mines))
            grid = engine.reset_with_mines(width, height, len(mines), mines)
            board = VirtualBoard(grid, len(mines), mines)
            self.assertEqual(board.static_bbbv(), oracle.static_bbbv(width, height, mines))
            counted = 0
            for raw in actions:
                before_playing = engine.status == GameStatus.PLAYING
                observed, _, _, _, _ = engine.step(raw[1], raw[2], getattr(Action, raw[0]))
                transition = board.step(EvidenceInput(*raw))
                counted += before_playing
                self.assertEqual(transition.observation, tuple(tuple(row) for row in observed))
                self.assertEqual(transition.counted, before_playing)
                self.assertEqual(board.outcome, None if engine.status == GameStatus.PLAYING else engine.status.name)
                counters = engine.get_counter_snapshot()
                self.assertEqual(counted, counters["active_clicks"] + counters["wasted_clicks"])
                oracle.EMIT("engine_transitions", {"fixture": index, "mines": mines, "action": raw,
                                                   "observation": observed, "counted": counted,
                                                   "outcome": board.outcome, "virtual_b": board.static_bbbv()})

    def test_public_pilot_world_independence_and_signature(self):
        grid = ((H, 1, H),)
        boards = [VirtualBoard(grid, 1, mines) for mines in (((0, 0),), ((2, 0),))]
        requests = [(board.observation, 1, 1, True) for board in boards]
        decisions = [pilot_p0(*request) for request in requests]
        self.assertEqual(requests[0], requests[1])
        self.assertEqual(decisions[0], decisions[1])
        self.assertIsNone(pilot_p0.__closure__)
        self.assertEqual(tuple(inspect.signature(pilot_p0).parameters),
                         ("observation", "num_mines", "counted_inputs", "allow_guess", "max_work", "cancelled"))
        oracle.EMIT("pilot_boundary", {"public_inputs": requests, "decisions": decisions,
                                      "evaluator_mines": [((0, 0),), ((2, 0),)]})

    def test_pilot_local_rules_density_flag_cost_and_unresolved(self):
        decision = pilot_p0(((F, 0, H),), 0, 9, False)
        self.assertEqual(decision.sequence, (EvidenceInput("OPEN", 2, 0),))
        decision = pilot_p0(((H, 1, H, 1, H, H, H),), 2, 2, True)
        self.assertEqual(decision.risk_hint, Fraction(2, 5))
        self.assertEqual(decision.sequence, (EvidenceInput("OPEN", 5, 0),))
        unresolved = pilot_p0(((H, 1, H),), 1, 1, False)
        self.assertEqual(unresolved.status, "PILOT_UNRESOLVED")
        self.assertFalse(unresolved.sequence)
        limited = pilot_p0(((H, H),), 0, 0, False, max_work=0)
        self.assertEqual(limited.reason, "PILOT_WORK_LIMIT")

    def test_terminal_rewards_include_c_flags_and_all_losses(self):
        grid = ((H, 1, H),)
        samples = (PosteriorSample(0, ((0, 0),)), PosteriorSample(1, ((2, 0),)))
        result = evaluate_rollouts(grid, 1, 1, True, samples, (candidate(("OPEN", 0, 0)),), target=Fraction(1, 2))
        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual([row.outcome for row in result.records], ["LOST", "WON"])
        self.assertEqual([row.value_x for row in result.records], [Fraction(0), Fraction(1, 2)])
        self.assertEqual([row.hit for row in result.records], [False, True])
        flagged = evaluate_rollouts(((F, 1, H),), 1, 2, True, samples,
                                   (candidate(("FLAG", 0, 0), ("OPEN", 0, 0)),))
        self.assertEqual(flagged.records[1].value_x, Fraction(1, 4))
        self.assertEqual(flagged.records[1].added_inputs, 2)

    def test_incomplete_nulls_and_partial_matrix(self):
        samples = (PosteriorSample(0, ((0, 0), (3, 0))),)
        result = evaluate_rollouts(((H, 1, H, H, H),), 2, 1, False, samples,
                                   (candidate(("OPEN", 4, 0)), candidate(("OPEN", 0, 0))))
        self.assertEqual(result.status, "INCOMPLETE")
        self.assertEqual(result.records[0].outcome, "PILOT_UNRESOLVED")
        self.assertIsNone(result.records[0].value_x)
        self.assertEqual(result.records[1].outcome, "NOT_STARTED")
        capped = evaluate_rollouts(((H, 1, H),), 1, 1, True, (PosteriorSample(0, ((2, 0),)),),
                                   (candidate(("OPEN", 0, 0)),), limits=RolloutLimits(max_virtual_inputs=0))
        self.assertEqual(capped.reason, "VIRTUAL_INPUT_LIMIT")
        self.assertIsNone(capped.records[0].value_x)

    def test_mismatched_world_cycle_cancel_and_error(self):
        grid = ((H, 1, H),)
        sample = (PosteriorSample(0, ((2, 0),)),)
        for cap in (RolloutLimits(max_rollouts=0), RolloutLimits(max_inputs_per_rollout=0),
                    RolloutLimits(max_seconds=0)):
            result = evaluate_rollouts(grid, 1, 1, True, sample,
                                       (candidate(("OPEN", 0, 0)),), limits=cap)
            self.assertEqual(result.status, "INCOMPLETE")
        cycle = evaluate_rollouts(grid, 1, 1, True, sample,
                                  (candidate(("FLAG", 0, 0), ("FLAG", 0, 0)),))
        self.assertEqual(cycle.status, "ERROR")
        wrong = evaluate_rollouts(grid, 1, 1, True, (PosteriorSample(0, ((1, 0),)),),
                                  (candidate(("OPEN", 0, 0)),))
        self.assertEqual(wrong.status, "ERROR")
        cancel = evaluate_rollouts(grid, 1, 1, True, sample, (candidate(("OPEN", 0, 0)),), cancelled=lambda: True)
        self.assertEqual(cancel.status, "CANCELLED")
        error = evaluate_rollouts(grid, 1, 1, True, sample, (candidate(("OPEN", 0, 0)),), cancelled=lambda: 1)
        self.assertEqual(error.status, "ERROR")
