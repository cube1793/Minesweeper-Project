"""Focused correctness tests for the isolated EXPERIMENTAL policy harness."""

from copy import deepcopy
from dataclasses import replace
from itertools import permutations
import json
from pathlib import Path
from random import Random
import tempfile
import unittest
from unittest.mock import patch

from benchmark_board import EXPERT_GENERAL_V1, generate_board
from core_engine import Action, CellState, MinesweeperEngine
from simple_algorithm import SimpleMove
from simple_decision import analyze_position
from experiments import stage3_policy_planner as p
from experiments import stage3_e_l_policy_pilot as h


H, F = int(CellState.HIDDEN), int(CellState.FLAGGED)


def plan(length, reveals, x=0, y=0, action=Action.OPEN):
    return p.Plan((SimpleMove(action, x, y),), length, reveals)


class ProfileTests(unittest.TestCase):
    def test_frozen_profile_and_reference_sources(self):
        self.assertEqual(p.load_table()[0][0], 126005)
        h.verify_sources()

    def test_profile_byte_tampering_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_bytes(p.PROFILE_PATH.read_bytes() + b" ")
            with self.assertRaisesRegex(p.PilotInvalid, "profile SHA"):
                p.load_table(path)

    def test_table_independently_checked(self):
        profile = json.loads(p.PROFILE_PATH.read_bytes())
        profile["timing_table_us"][0][0] += 1
        raw = p.canonical_bytes(profile)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_bytes(raw)
            with patch.object(p, "PROFILE_SHA256", p.hashlib.sha256(raw).hexdigest()):
                with self.assertRaisesRegex(p.PilotInvalid, "table SHA"):
                    p.load_table(path)

    def test_source_drift_fails_closed(self):
        with patch.object(h, "source_hash", return_value="wrong"):
            with self.assertRaisesRegex(p.PilotInvalid, "source mismatch"):
                h.verify_sources()

    def test_startup_failure_creates_invalid_artifact_without_generating_board(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(h, "OUTPUT_ROOT", Path(directory)), \
                 patch.object(h, "load_table", side_effect=p.PilotInvalid("bad profile")), \
                 patch.object(h, "generate_board") as generator:
                result = h.run_pilot("smoke100", Path(directory) / "run")
                self.assertEqual(result["status"], "INVALID")
                self.assertIsNone(result["primary_policy_result"])
                generator.assert_not_called()
                self.assertEqual(json.loads((Path(directory) / "run/summary.json").read_bytes()), result)


class PlannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = p.load_table()

    def test_exact_route_matches_exhaustive_oracle(self):
        rng = Random(751)
        for n in range(8):
            cells = rng.sample([(x, y) for y in range(4) for x in range(5)], n + 2)
            cursor, goal, *flags = cells
            terminal = SimpleMove(Action.CHORD, *goal)
            actions, actual = p.exact_route(self.table, cursor, flags, terminal)
            expected = min((sum(p.cost(self.table, a, b) for a, b in
                                    zip((cursor,) + route, route + (goal,))),
                            tuple(p.reading(c) for c in route)) for route in permutations(flags))
            self.assertEqual((actual, tuple((m.y, m.x) for m in actions[:-1])), expected)
            self.assertEqual(actions[-1], terminal)

    def test_route_optimizes_table_including_terminal_not_distance_or_greedy(self):
        table = tuple(tuple(1 for _ in range(16)) for _ in range(30))
        table = list(map(list, table))
        table[1][0], table[2][0], table[3][0] = 10, 1, 1
        actions, length = p.exact_route(table, (0, 0), {(1, 0), (2, 0)},
                                        SimpleMove(Action.OPEN, 4, 0))
        self.assertEqual([(m.x, m.y) for m in actions], [(2, 0), (1, 0), (4, 0)])
        self.assertEqual(length, 12)

    def test_routing_ties_are_reading_order(self):
        table = tuple(tuple(1 for _ in range(16)) for _ in range(30))
        moves, _ = p.exact_route(table, (0, 0), {(1, 1), (2, 0), (1, 0)},
                                 SimpleMove(Action.OPEN, 3, 3))
        self.assertEqual([(m.x, m.y) for m in moves[:-1]], [(1, 0), (2, 0), (1, 1)])

    def test_e_l_tradeoff_and_exact_comparison_above_float_precision(self):
        plans = (plan(50, 1), plan(350, 8, x=1))
        self.assertEqual(p.remove_dominated(plans), plans)
        self.assertEqual(p.select_plan(plans, "E-FIRST")[0], plans[1])
        self.assertEqual(p.select_plan(plans, "L-FIRST")[0], plans[0])
        self.assertLess(p.compare_e(plan(2**60, 1), plan(2**60 + 1, 1)), 0)
        self.assertEqual(p.compare_e(plan(3, 2), plan(6, 4)), 0)

    def test_e_tie_then_l_then_common_fallback(self):
        a, b = plan(30, 2), plan(60, 4, x=1)
        chosen, diagnostic = p.select_plan((b, a), "E-FIRST")
        self.assertEqual(chosen, a)
        self.assertTrue(diagnostic["exact_e_tie"])
        self.assertFalse(diagnostic["final_fallback"])
        tied = (plan(30, 2, x=1), plan(30, 2, y=1))
        for policy in p.POLICIES:
            self.assertEqual(p.select_plan(tuple(reversed(tied)), policy)[0], tied[0])
            self.assertTrue(p.select_plan(tied, policy)[1]["final_fallback"])

    def test_dominance_preserves_equal_metrics(self):
        a, b, c, d = plan(10, 2), plan(11, 2), plan(10, 1), plan(10, 2, x=1)
        self.assertEqual(p.remove_dominated((a, b, c, d)), (a, d))

    def test_local_path_never_calls_probability(self):
        with patch("simple_decision.calculate_probabilities", side_effect=AssertionError):
            decision = p.plan_position([[1, H, 1, H]], 1, (0, 0), self.table, "E-FIRST")
        self.assertEqual(decision.move, SimpleMove(Action.FLAG, 1, 0))
        self.assertIsNone(decision.evidence.probability_result)

    def test_virtual_open_and_chord_require_actual_setup_first(self):
        observation = [[1, H, 1, H]]
        original = deepcopy(observation)
        decision = p.plan_position(observation, 1, (0, 0), self.table, "E-FIRST")
        self.assertEqual(observation, original)
        self.assertEqual({q.actions[-1].action for q in decision.candidates}, {Action.OPEN, Action.CHORD})
        for candidate in decision.candidates:
            self.assertEqual(candidate.actions[0], SimpleMove(Action.FLAG, 1, 0))
            self.assertEqual(candidate.reveals, 1)
        invalid = replace(decision, move=SimpleMove(Action.OPEN, 3, 0))
        with self.assertRaisesRegex(p.PilotInvalid, "virtual-only"):
            h.validate_first_action(observation, invalid)
        next_decision = p.plan_position([[1, F, 1, H]], 1, (1, 0), self.table, "E-FIRST")
        h.validate_first_action([[1, F, 1, H]], next_decision)
        self.assertTrue(all(len(q.actions) == 1 for q in next_decision.candidates))

    def test_chord_direct_reveal_count_no_flood_prediction(self):
        observation = [[F, 1, H], [1, 1, H]]
        decision = p.plan_position(observation, 1, (1, 0), self.table, "E-FIRST")
        chord = [q for q in decision.candidates if q.actions[-1].action == Action.CHORD]
        self.assertTrue(chord)
        self.assertTrue(all(q.reveals == 2 for q in chord))
        self.assertTrue(all(q.reveals == 1 for q in decision.candidates
                            if q.actions[-1].action == Action.OPEN))

    def test_zero_clue_and_empty_chord_excluded(self):
        decision = p.plan_position([[0, H]], 0, (0, 0), self.table, "E-FIRST")
        self.assertTrue(all(q.actions[-1].action == Action.OPEN for q in decision.candidates))
        decision = p.plan_position([[1, H]], 1, (0, 0), self.table, "E-FIRST")
        self.assertEqual(decision.reason, "flag_fallback")
        self.assertEqual(decision.candidates, ())

    def test_nearest_flag_fallback_uses_table_then_reading_tie(self):
        observation = [[H, 1, 0, 1, H]]
        decision = p.plan_position(observation, 2, (3, 0), self.table, "E-FIRST")
        self.assertEqual(decision.move, SimpleMove(Action.FLAG, 4, 0))
        tied = p.plan_position(observation, 2, (2, 0), self.table, "L-FIRST")
        self.assertEqual(tied.move, SimpleMove(Action.FLAG, 0, 0))
        self.assertEqual(tied.selection_diagnostics["flag_fallback_ties"], 2)

    def test_global_certainty_and_guess_stage2_tie_are_preserved(self):
        certainty = p.plan_position([[H, H]], 0, (1, 0), self.table, "E-FIRST")
        self.assertEqual(len(certainty.candidates), 2)
        guess = p.plan_position([[H, H, H]], 1, (2, 0), self.table, "E-FIRST")
        self.assertEqual(guess.move, SimpleMove(Action.OPEN, 0, 0))
        cp = h.guess_checkpoint([[H, H, H]], guess.evidence, 0)
        self.assertEqual(cp["minimum_mine_probability"], h.rational(1, 3))
        wrong = replace(guess.evidence, move=SimpleMove(Action.OPEN, 2, 0))
        with self.assertRaisesRegex(p.PilotInvalid, "minimum risk"):
            h.guess_checkpoint([[H, H, H]], wrong, 0)


class ExecutionAndGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = p.load_table()

    def test_terminal_first_open_and_auto_flags_cost_only_one_input(self):
        engine = MinesweeperEngine(1, 1, 0)
        records = []
        terminal = next(h.policy_game(engine, "E-FIRST", self.table, records.append))
        self.assertEqual(terminal["final_result"], "WON")
        self.assertEqual(terminal["total_time_us"], 126005)
        self.assertEqual(len(records), 1)

    def test_execute_only_first_action_then_fresh_complete_replan(self):
        engine = MinesweeperEngine(4, 1, 1)
        engine.reset_with_mines(4, 1, 1, {(1, 0)})
        records, observations = [], []
        actual_plan = h.plan_position

        def traced(observation, *args):
            self.assertEqual(observation, engine.get_observation())
            observations.append(deepcopy(observation))
            return actual_plan(observation, *args)

        with patch.object(h, "plan_position", side_effect=traced):
            stream = h.policy_game(engine, "E-FIRST", self.table, records.append)
            checkpoints = list(stream)
        self.assertEqual(len(observations), len(records) - 1)
        self.assertEqual(checkpoints[-1]["final_result"], "WON")
        self.assertEqual(checkpoints[-1]["total_time_us"], sum(r["cost_us"] for r in records))
        self.assertEqual(records[-1]["status_after"], "WON")
        self.assertEqual(checkpoints[-1]["action_counts"].get("FLAG", 0), 1)

    def test_loss_cost_includes_last_guess_and_no_post_terminal_actions(self):
        engine = MinesweeperEngine(3, 1, 1)
        engine.reset_with_mines(3, 1, 1, {(1, 0)})
        # Canonical OPEN proves cell 1 mine; FLAG, then certain OPEN wins here.
        # A 2x2 corner clue gives a true three-way guess with fixed (y,x) tie.
        engine = MinesweeperEngine(2, 2, 1)
        engine.reset_with_mines(2, 2, 1, {(1, 0)})
        records = []
        stream = h.policy_game(engine, "E-FIRST", self.table, records.append)
        cp = next(stream)
        self.assertEqual(cp["kind"], "guess")
        self.assertEqual(len(records), 1)  # guess is not committed at yield
        terminal = next(stream)
        self.assertEqual(terminal["final_result"], "LOST")
        self.assertEqual(terminal["total_time_us"], 252010)
        self.assertEqual(len(records), 2)
        self.assertEqual(list(stream), [])

    def test_hard_gate_rejects_every_required_difference(self):
        decision = analyze_position([[H, H]], 1)
        cp = h.guess_checkpoint([[H, H]], decision, 0)
        mutations = {"observation": [[H, F]], "minimum_mine_probability": h.rational(1, 3),
                     "selected_coordinate": [1, 0], "guess_index": 1}
        for field, value in mutations.items():
            with self.subTest(field=field), self.assertRaises(p.PilotInvalid):
                h.check_equal(cp, {**cp, field: value}, "test")
        terminal = {"kind": "terminal", "final_result": "WON", "guess_count": 1}
        for field, value in (("final_result", "LOST"), ("guess_count", 2)):
            with self.subTest(field=field), self.assertRaises(p.PilotInvalid):
                h.check_equal(terminal, {**terminal, field: value}, "test")

    def test_pair_mismatch_stops_before_any_guess_commits(self):
        commits = []

        def stream(engine, policy, table, emit):
            yield {"kind": "guess", "selected_coordinate": [int(policy == "E-FIRST"), 0]}
            commits.append(policy)

        with patch.object(h, "policy_game", side_effect=stream):
            with self.assertRaisesRegex(p.PilotInvalid, "hard gate"):
                h.compare_game(generate_board(EXPERT_GENERAL_V1, h.START), self.table,
                               lambda *a: None, lambda *a: None)
        self.assertEqual(commits, [])

    def test_small_real_pair_matches_actual_frozen_runner_and_cost_replay(self):
        board = generate_board(EXPERT_GENERAL_V1, h.START)
        records = {policy: [] for policy in p.POLICIES}
        pair = h.compare_game(board, self.table,
                              lambda policy, r: records[policy].append(r), lambda *a: None,
                              h.stage2_reference(board))
        self.assertTrue(pair["stage2_cross_checked"])
        for policy, stream in records.items():
            cursor, total = (0, 0), 0
            for record in stream:
                move = record["move"]
                destination = (move["x"], move["y"])
                total += p.cost(self.table, cursor, destination)
                cursor = destination
                self.assertEqual(total, record["cumulative_time_us"])
            self.assertEqual(pair["policies"][policy]["total_time_us"], total)

    def test_nearest_rank_and_exact_ratios_serialize_canonically(self):
        self.assertEqual(h.distribution(h.Counter({1: 1, 2: 98, 3: 1}))["P99"], 2)
        value = {"ratio": h.rational(4, 6), "integer": 2**100}
        self.assertEqual(json.loads(p.canonical_bytes(value)), value)
        self.assertEqual(p.canonical_bytes(value), p.canonical_bytes(dict(reversed(list(value.items())))))


if __name__ == "__main__":
    unittest.main()
