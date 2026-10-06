"""Independent Stage-3 execution checks; answers only arrange engine fixtures."""

import ast
import inspect
import unittest
from dataclasses import FrozenInstanceError, replace
from itertools import product
from random import Random
from unittest.mock import patch

from core_engine import Action, CellState, GameStatus, MinesweeperEngine
from simple_algorithm import SimpleMove
from simple_decision import DecisionKind, analyze_position
from simple_runner import _action_effect_deltas as stage2_deltas
from stage3_physical import action_cost, load_timing_table
from stage3_planner import Stage3Decision, plan_position
from stage3_runner import (
    Stage3RunnerError, _action_effect_deltas, _validate_execution, run_stage3,
)


H, F = CellState.HIDDEN, CellState.FLAGGED


def fixed_engine(width=4, height=1, mines=frozenset({(1, 0)})):
    engine = MinesweeperEngine(width, height, len(mines))
    engine.reset_with_mines(width, height, len(mines), mines)
    return engine


class PublicEngineView:
    """Expose exactly the public runner boundary; forbidden reads raise."""

    __slots__ = ("__engine",)

    def __init__(self, engine):
        self.__engine = engine

    @property
    def width(self):
        return self.__engine.width

    @property
    def height(self):
        return self.__engine.height

    @property
    def num_mines(self):
        return self.__engine.num_mines

    @property
    def status(self):
        return self.__engine.status

    def get_observation(self):
        return self.__engine.get_observation()

    def step(self, x, y, action):
        return self.__engine.step(x, y, action)

    def __getattr__(self, name):
        raise AssertionError(f"Runner accessed nonpublic input: {name}")


class Stage3RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = load_timing_table()

    def test_canonical_first_open_cost_no_decision(self):
        result = run_stage3(fixed_engine(), table=self.table)
        first = result.traces[0]
        self.assertEqual(first.move, SimpleMove(Action.OPEN, 0, 0))
        self.assertEqual(first.cursor_before, (0, 0))
        self.assertEqual(first.modeled_action_us, 126005)
        self.assertIsNone(first.decision)
        self.assertIsNone(first.decision_compute_ns)
        self.assertEqual(result.total_modeled_us, sum(item.modeled_action_us for item in result.traces))

    def test_terminal_first_open_win_and_auto_flags_have_no_cost(self):
        engine = fixed_engine(3, 1, frozenset({(2, 0)}))
        with patch("stage3_runner.plan_position", side_effect=AssertionError("unexpected planning")):
            result = run_stage3(engine, table=self.table)
        self.assertEqual(result.status, GameStatus.WON)
        self.assertEqual(result.moves, (SimpleMove(Action.OPEN, 0, 0),))
        self.assertEqual(result.total_modeled_us, 126005)
        self.assertEqual(engine.get_observation(), [[0, 1, F]])
        self.assertEqual(result.traces[0].safe_cells_opened_delta, 2)
        self.assertEqual(result.traces[0].explicit_flag_delta, 0)

    def test_terminal_first_open_loss_includes_final_input(self):
        engine = fixed_engine(2, 1, frozenset({(0, 0)}))
        with patch("stage3_runner.plan_position", side_effect=AssertionError("unexpected planning")):
            result = run_stage3(engine, table=self.table)
        self.assertEqual(result.status, GameStatus.LOST)
        self.assertEqual(len(result.traces), 1)
        self.assertEqual(result.total_modeled_us, 126005)
        self.assertEqual(result.traces[0].safe_cells_opened_delta, 0)

    def test_complete_plan_step_fresh_observation_alternate_with_cursor(self):
        engine = fixed_engine()
        original_step = engine.step
        original_observation = engine.get_observation
        events, actual_targets, calls = [], [], []

        def observe():
            observation = original_observation()
            events.append("observation")
            return observation

        def plan(observation, num_mines, cursor, table):
            self.assertEqual(events[-1], "observation")
            self.assertEqual(observation, original_observation())
            self.assertEqual(cursor, actual_targets[-1])
            self.assertEqual(num_mines, engine.num_mines)
            events.append("plan")
            decision = plan_position(observation, num_mines, cursor, table)
            calls.append(decision)
            return decision

        def step(x, y, action):
            self.assertEqual(events[-1], "plan" if actual_targets else "observation")
            if actual_targets:
                self.assertEqual(calls[-1].move, SimpleMove(action, x, y))
            events.append("step")
            actual_targets.append((x, y))
            return original_step(x, y, action)

        with patch.object(engine, "get_observation", side_effect=observe), \
             patch.object(engine, "step", side_effect=step), \
             patch("stage3_runner.plan_position", side_effect=plan):
            result = run_stage3(engine, table=self.table)
        self.assertEqual(len(calls), len(result.traces) - 1)
        self.assertEqual(events[-1], "observation")
        self.assertTrue(all(trace.decision is calls[index] for index, trace in enumerate(result.traces[1:])))
        for before, after in zip(result.traces, result.traces[1:]):
            self.assertEqual(after.cursor_before, (before.move.x, before.move.y))

    def test_flag_triggers_full_replan_then_chord_executes(self):
        result = run_stage3(fixed_engine(), table=self.table)
        self.assertEqual(result.moves, (
            SimpleMove(Action.OPEN, 0, 0), SimpleMove(Action.FLAG, 1, 0),
            SimpleMove(Action.OPEN, 2, 0), SimpleMove(Action.CHORD, 2, 0),
        ))
        self.assertEqual([trace.decision.evidence.kind for trace in result.traces[1:]], [
            DecisionKind.LOCAL_DETERMINISTIC, DecisionKind.GLOBAL_CERTAINTY,
            DecisionKind.LOCAL_DETERMINISTIC,
        ])
        self.assertEqual([trace.explicit_flag_delta for trace in result.traces], [0, 1, 0, 0])
        self.assertEqual([trace.safe_cells_opened_delta for trace in result.traces], [1, 0, 1, 1])
        self.assertEqual(result.traces[-1].cursor_before, (2, 0))
        self.assertEqual(result.traces[-1].modeled_action_us, 126005)

    def test_setup_suffix_is_discarded_when_fresh_plan_changes(self):
        engine = fixed_engine(6, 4, frozenset({(1, 2), (2, 1), (4, 0), (4, 1), (4, 2)}))
        public_calls = []

        def plan(observation, num_mines, cursor, table):
            self.assertEqual(observation, engine.get_observation())
            public_calls.append((tuple(tuple(row) for row in observation), cursor))
            return plan_position(observation, num_mines, cursor, table)

        with patch("stage3_runner.plan_position", side_effect=plan) as planner:
            result = run_stage3(engine, table=self.table)
        setup_trace = result.traces[4]
        self.assertEqual(setup_trace.decision.plan.actions, (
            SimpleMove(Action.FLAG, 2, 1), SimpleMove(Action.FLAG, 1, 2),
            SimpleMove(Action.CHORD, 2, 2),
        ))
        self.assertEqual(setup_trace.move, SimpleMove(Action.FLAG, 2, 1))
        # A genuinely new public inference unlocks a preferable OPEN. Executing
        # a queued setup suffix would incorrectly FLAG (1,2) at this point.
        self.assertEqual(result.traces[5].move, SimpleMove(Action.OPEN, 2, 0))
        self.assertEqual(public_calls[4][0][1][2], F)
        self.assertEqual(public_calls[4][1], (2, 1))
        self.assertEqual(planner.call_count, len(result.traces) - 1)

    def test_analysis_and_planning_timer_covers_the_whole_planner_call(self):
        times = iter((100, 180, 200, 390, 400, 510))
        boundaries = []

        def tick():
            boundaries.append("clock")
            return next(times)

        def plan(*args):
            boundaries.append("analysis+planning")
            return plan_position(*args)

        with patch("stage3_runner.perf_counter_ns", side_effect=tick), \
             patch("stage3_runner.plan_position", side_effect=plan):
            result = run_stage3(fixed_engine(), table=self.table)
        self.assertEqual([trace.decision_compute_ns for trace in result.traces], [None, 80, 190, 110])
        self.assertEqual(result.total_modeled_us, 4 * 126005)
        self.assertEqual(boundaries, ["clock", "analysis+planning", "clock"] * 3)

    def test_terminal_guess_exact_coordinate_and_cost_included(self):
        result = run_stage3(fixed_engine(5, 1, frozenset({(1, 0), (2, 0)})), table=self.table)
        last = result.traces[-1]
        self.assertEqual(result.status, GameStatus.LOST)
        self.assertEqual(last.move, SimpleMove(Action.OPEN, 2, 0))
        self.assertEqual(last.move, last.decision.evidence.move)
        self.assertEqual(last.decision.evidence.kind, DecisionKind.PROBABILITY_GUESS)
        self.assertEqual(last.modeled_action_us, 126005)
        self.assertEqual(result.total_modeled_us, 3 * 126005)

    def test_already_terminal_receives_no_actions_analysis_or_observation(self):
        for mines in (frozenset({(0, 0)}), frozenset({(2, 0)})):
            engine = fixed_engine(3, 1, mines)
            engine.step(0, 0, Action.OPEN)
            with self.subTest(status=engine.status):
                self.assertIn(engine.status, (GameStatus.WON, GameStatus.LOST))
                with patch.object(engine, "step", side_effect=AssertionError("step")), \
                     patch.object(engine, "get_observation", side_effect=AssertionError("observe")), \
                     patch("stage3_runner.plan_position", side_effect=AssertionError("plan")):
                    result = run_stage3(engine, table=self.table)
                self.assertEqual(result.moves, ())
                self.assertEqual(result.total_modeled_us, 0)

    def test_progressed_nonterminal_start_rejected(self):
        engine = fixed_engine()
        engine.step(0, 0, Action.OPEN)
        with self.assertRaisesRegex(ValueError, "entirely HIDDEN"):
            run_stage3(engine, table=self.table)

    def test_unsupported_board_dimensions_rejected(self):
        for width, height in ((31, 1), (1, 17)):
            with self.subTest(width=width, height=height):
                with self.assertRaisesRegex(ValueError, "30-by-16"):
                    run_stage3(fixed_engine(width, height, frozenset({(0, 0)})), table=self.table)

    def test_deterministic_actions_and_replay_on_fixed_boards(self):
        outcomes = set()
        for seed in range(12):
            rng = Random(seed)
            candidates = [(x, y) for y in range(4) for x in range(6) if (x, y) != (0, 0)]
            mines = frozenset(rng.sample(candidates, 5))
            with self.subTest(seed=seed):
                first_engine = fixed_engine(6, 4, mines)
                first = run_stage3(first_engine, table=self.table)
                second = run_stage3(fixed_engine(6, 4, mines), table=self.table)
                self.assertEqual(first.moves, second.moves)
                self.assertEqual(first.total_modeled_us, second.total_modeled_us)
                self.assertEqual(first.status, second.status)
                self.assertEqual(tuple(replace(trace, decision_compute_ns=None) for trace in first.traces),
                                 tuple(replace(trace, decision_compute_ns=None) for trace in second.traces))
                replay = fixed_engine(6, 4, mines)
                cursor = (0, 0)
                independently_summed_cost = 0
                for move in first.moves:
                    self.assertEqual(replay.status, GameStatus.PLAYING)
                    independently_summed_cost += self.table[abs(move.x - cursor[0])][abs(move.y - cursor[1])]
                    replay.step(move.x, move.y, move.action)
                    cursor = (move.x, move.y)
                self.assertEqual(first_engine.get_observation(), replay.get_observation())
                self.assertEqual(first.status, replay.status)
                self.assertEqual(first.total_modeled_us, independently_summed_cost)
                outcomes.add(first.status)
        self.assertEqual(outcomes, {GameStatus.WON, GameStatus.LOST})

    def test_public_information_boundary(self):
        result = run_stage3(PublicEngineView(fixed_engine()), table=self.table)
        self.assertEqual(result.status, GameStatus.WON)
        source = inspect.getsource(run_stage3) + inspect.getsource(_validate_execution)
        attributes = {node.attr for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Attribute)}
        for forbidden in ("get_board_snapshot", "get_counter_snapshot", "get_stats", "_mines", "fingerprint"):
            self.assertNotIn(forbidden, attributes)

    def test_public_delta_helper_matches_stage2_exhaustive_single_cell_transitions(self):
        values = (H, F, *range(9), CellState.MINE, CellState.EXPLODED, CellState.FALSE_FLAG)
        for old, new, action in product(values, values, (Action.OPEN, Action.FLAG, Action.CHORD)):
            move = SimpleMove(action, 0, 0)
            self.assertEqual(_action_effect_deltas([[old]], [[new]], move),
                             stage2_deltas([[old]], [[new]], move))

    def test_observer_receives_exact_immutable_traces(self):
        seen = []
        result = run_stage3(fixed_engine(), table=self.table, observer=seen.append)
        self.assertEqual(tuple(seen), result.traces)
        with self.assertRaises(FrozenInstanceError):
            seen[0].modeled_action_us = 0
        with self.assertRaises(FrozenInstanceError):
            result.status = GameStatus.PLAYING
        self.assertTrue(all(type(trace.modeled_action_us) is int for trace in seen))

    def test_observer_errors_propagate(self):
        engine = fixed_engine()
        with self.assertRaisesRegex(RuntimeError, "observer failed"):
            run_stage3(engine, table=self.table,
                       observer=lambda trace: (_ for _ in ()).throw(RuntimeError("observer failed")))
        self.assertEqual(engine.get_observation()[0][0], 1)

    def test_invalid_table_rejected_before_first_input(self):
        table = [list(row) for row in self.table]
        table[0][0] = 1
        engine = fixed_engine()
        with patch.object(engine, "step", side_effect=AssertionError("step")):
            with self.assertRaisesRegex(ValueError, "table SHA-256"):
                run_stage3(engine, table=table)

    def test_no_progress_and_absent_plan_fail_closed(self):
        engine = fixed_engine()
        with patch.object(engine, "step", return_value=None):
            with self.assertRaisesRegex(Stage3RunnerError, "no progress"):
                run_stage3(engine, table=self.table)
        with patch("stage3_runner.plan_position", return_value=None):
            with self.assertRaisesRegex(Stage3RunnerError, "no action"):
                run_stage3(fixed_engine(), table=self.table)

    def test_execution_rejects_uncertain_flag_and_unproved_open(self):
        observation = [[1, H, H]]
        evidence = analyze_position(observation, 1)
        for move in (SimpleMove(Action.OPEN, 1, 0), SimpleMove(Action.FLAG, 2, 0)):
            with self.subTest(move=move):
                decision = Stage3Decision(evidence=evidence, move=move, plan=None)
                with self.assertRaises(Stage3RunnerError):
                    _validate_execution(observation, move, decision)

    def test_execution_rejects_virtual_chord_until_setup_is_physical(self):
        observation = [[1, H, H]]
        move = SimpleMove(Action.CHORD, 0, 0)
        decision = Stage3Decision(evidence=analyze_position(observation, 1), move=move, plan=None)
        with self.assertRaisesRegex(Stage3RunnerError, "CHORD"):
            _validate_execution(observation, move, decision)

    def test_execution_rejects_stale_public_constraints(self):
        evidence = analyze_position([[1, H, H]], 1)
        move = SimpleMove(Action.FLAG, 1, 0)
        decision = Stage3Decision(evidence=evidence, move=move, plan=None)
        with self.assertRaisesRegex(Stage3RunnerError, "current observation"):
            _validate_execution([[1, F, H]], move, decision)

    def test_execution_rejects_alternate_equal_risk_guess(self):
        observation = [[H, H, H]]
        evidence = analyze_position(observation, 1)
        move = SimpleMove(Action.OPEN, 2, 0)
        decision = Stage3Decision(evidence=evidence, move=move, plan=None)
        with self.assertRaisesRegex(Stage3RunnerError, "exact Stage-2 guess"):
            _validate_execution(observation, move, decision)


if __name__ == "__main__":
    unittest.main()
