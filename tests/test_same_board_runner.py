"""Real small-board execution, native evidence retention and failure boundaries."""

import subprocess
import sys
import unittest
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
from unittest.mock import patch

import same_board_runner as comparison
from benchmark_modeled_time import ModeledTimeValidationError
from core_engine import Action, CellState, GameStatus
from mouse_trace import MouseTraceData, MouseTracePoint, MouseTraceSegment
from replay_model import ReplayBoard, ReplayData, ReplayEvent
from replay_player import ReplayPlayer
from same_board_comparison import ComparisonLayout, HumanComparisonContext
from same_board_runner import ActionCounts, ComparisonExecutionError, run_same_board_comparison
from simple_decision import analyze_position
from simple_runner import SimpleRunnerError, StopReason, run_simple
from stage3_planner import plan_position
from stage3_runner import run_stage3


def human_context(*, mined_origin=False, with_trace=False, prelude=False):
    if mined_origin:
        board = ReplayBoard(2, 2, 1, {(0, 0)})
        inputs = (("OPEN", 1, 0), ("OPEN", 0, 1), ("OPEN", 1, 1))
    else:
        board = ReplayBoard(4, 1, 1, {(1, 0)})
        inputs = (("OPEN", 0, 0), ("OPEN", 2, 0), ("OPEN", 3, 0))
        if prelude:
            inputs = (("CHORD", 0, 0), ("FLAG", 1, 0), ("FLAG", 1, 0),
                      ("OPEN", 0, 0), ("OPEN", 0, 0), ("OPEN", 2, 0), ("OPEN", 3, 0))
    replay = ReplayData(board, tuple(
        ReplayEvent(index * 6.25, x, y, action) for index, (action, x, y) in enumerate(inputs)
    ))
    if with_trace:
        trace = MouseTraceData(board.width, board.height, (MouseTraceSegment(20, (
            MouseTracePoint(0, replay.events[0].x * 20 + 10.25, 10.5, 0),
            MouseTracePoint(56789, replay.events[-1].x * 20 + 10, replay.events[-1].y * 20 + 10,
                            len(replay.events) - 1),
        )),))
        replay = replace(replay, schema_version=2, mouse_trace=trace)
    return HumanComparisonContext(replay, declared_full_game_human=True)


class SameBoardExecutionTests(unittest.TestCase):
    def test_safe_origin_native_results_counts_and_reconstruction(self):
        result = run_same_board_comparison(human_context())
        self.assertEqual(result.stage2_metrics.outcome, GameStatus.WON)
        self.assertEqual(result.stage3_metrics.outcome, GameStatus.WON)
        self.assertEqual(result.human_metrics.actions, ActionCounts(3, 3, 0, 0))
        self.assertEqual(result.stage2_metrics.actions, ActionCounts(4, 3, 1, 0))
        self.assertEqual(result.stage3_metrics.actions, ActionCounts(4, 2, 1, 1))
        self.assertEqual(ComparisonLayout(result.stage2_result.replay_data.board), result.context.layout)
        player = ReplayPlayer(result.stage2_result.replay_data)
        for trace in result.stage2_traces:
            player.next()
            self.assertEqual(player.engine.status, trace.status_after)
        self.assertEqual(player.engine.status, result.stage2_result.status)
        self.assertEqual(result.stage3_result.traces[-1].status_after, result.stage3_result.status)

    def test_both_engines_are_fresh_isolated_and_only_existing_solver_arguments_are_used(self):
        context = human_context(with_trace=True)
        engines, native_results, stage2_traces = [], [], []

        def check_engine(engine):
            engines.append(engine)
            snapshot = engine.get_board_snapshot()
            self.assertTrue(snapshot.mines_placed)
            self.assertEqual((snapshot.width, snapshot.height, snapshot.num_mines, snapshot.mines),
                             (4, 1, 1, context.layout.board.mine_positions))
            self.assertEqual(engine.status, GameStatus.PLAYING)
            self.assertEqual(engine.get_observation(), [[CellState.HIDDEN] * 4])

        def stage2(engine, *, accept_guesses, initial_open, observer):
            check_engine(engine)
            self.assertIs(accept_guesses, True)
            self.assertEqual(initial_open, (0, 0))

            def capture(trace):
                stage2_traces.append(trace)
                observer(trace)

            result = run_simple(engine, accept_guesses=accept_guesses, initial_open=initial_open, observer=capture)
            native_results.append(result)
            return result

        def stage3(engine, *, table):
            check_engine(engine)
            result = run_stage3(engine, table=table)
            native_results.append(result)
            return result

        # Signatures enforce public inference boundaries; no Human stream,
        # trace, fingerprint or answer-layout argument can reach either planner.
        def analyze(observation, num_mines):
            self.assertTrue(all(type(cell) is int for row in observation for cell in row))
            return analyze_position(observation, num_mines)

        def plan(observation, num_mines, cursor, table):
            self.assertTrue(all(type(cell) is int for row in observation for cell in row))
            return plan_position(observation, num_mines, cursor, table)

        with patch("same_board_runner.run_simple", side_effect=stage2) as s2, \
             patch("same_board_runner.run_stage3", side_effect=stage3) as s3, \
             patch("simple_runner.analyze_position", side_effect=analyze), \
             patch("stage3_runner.plan_position", side_effect=plan), \
             patch("core_engine.random.sample", side_effect=AssertionError("regeneration")), \
             patch("benchmark_board.generate_board", side_effect=AssertionError("benchmark generation")), \
             patch("sqlite3.connect", side_effect=AssertionError("database")), \
             patch("same_board_runner.authenticate_model_c", wraps=comparison.authenticate_model_c) as auth:
            result = run_same_board_comparison(context)
        self.assertIsNot(engines[0], engines[1])
        self.assertIs(result.stage2_result, native_results[0])
        self.assertIs(result.stage3_result, native_results[1])
        for collected, retained in zip(stage2_traces, result.stage2_traces):
            self.assertIs(collected, retained)
        self.assertIs(result.context, context)
        self.assertEqual((s2.call_count, s3.call_count, auth.call_count), (1, 1, 1))

    def test_human_win_elsewhere_both_solvers_lose_at_mined_origin_without_retry(self):
        context = human_context(mined_origin=True)
        with patch("same_board_runner.run_simple", wraps=run_simple) as s2, \
             patch("same_board_runner.run_stage3", wraps=run_stage3) as s3, \
             patch("simple_runner.analyze_position", side_effect=AssertionError("decision after loss")), \
             patch("stage3_runner.plan_position", side_effect=AssertionError("decision after loss")), \
             patch("core_engine.random.sample", side_effect=AssertionError("regeneration")):
            result = run_same_board_comparison(context)
        self.assertEqual(context.first_open_event.x, 1)
        self.assertEqual(result.human_metrics.outcome, GameStatus.WON)
        for traces, metrics in ((result.stage2_traces, result.stage2_metrics),
                                (result.stage3_result.traces, result.stage3_metrics)):
            self.assertEqual(len(traces), 1)
            self.assertEqual((traces[0].move.action, traces[0].move.x, traces[0].move.y), (Action.OPEN, 0, 0))
            self.assertEqual(metrics.outcome, GameStatus.LOST)
            self.assertEqual(metrics.model_c_total_us, result.model_c_evaluation.table[0][0])
            self.assertIsNone(traces[0].decision_compute_ns)
            self.assertIsNone(traces[0].decision)
            self.assertEqual(metrics.decision_compute_total_ns, 0)  # Empty sum, not a decision measurement.
        self.assertEqual((s2.call_count, s3.call_count), (1, 1))

    def test_stage2_total_includes_first_and_terminal_inputs_stage3_keeps_recorded_total(self):
        result = run_same_board_comparison(human_context())
        table = result.model_c_evaluation.table
        self.assertEqual(result.stage2_metrics.model_c_total_us, table[0][0] + 3 * table[1][0])
        self.assertEqual(result.stage3_metrics.model_c_total_us, 2 * table[0][0] + 2 * table[1][0])
        self.assertEqual(result.stage3_metrics.model_c_total_us, result.stage3_result.total_modeled_us)
        self.assertEqual(result.stage3_metrics.model_c_total_us,
                         sum(t.modeled_action_us for t in result.stage3_result.traces))
        self.assertIs(type(result.stage2_metrics.model_c_total_us), int)
        self.assertIs(type(result.stage3_metrics.model_c_total_us), int)

    def test_compute_totals_sum_actual_non_none_measurements_and_keep_first_none(self):
        with patch("simple_runner.perf_counter_ns", side_effect=(10, 17, 20, 31, 40, 53)), \
             patch("stage3_runner.perf_counter_ns", side_effect=(100, 105, 200, 207, 300, 311)):
            result = run_same_board_comparison(human_context())
        self.assertEqual([t.decision_compute_ns for t in result.stage2_traces], [None, 7, 11, 13])
        self.assertEqual([t.decision_compute_ns for t in result.stage3_result.traces], [None, 5, 7, 11])
        self.assertEqual(result.stage2_metrics.decision_compute_total_ns, 31)
        self.assertEqual(result.stage3_metrics.decision_compute_total_ns, 23)

    def test_human_prelude_wasted_actions_and_elapsed_authority_are_preserved(self):
        context = human_context(prelude=True)
        result = run_same_board_comparison(context)
        self.assertEqual(result.human_metrics.actions, ActionCounts(7, 4, 2, 1))
        self.assertEqual(result.human_metrics.replay_elapsed_seconds, 37.5)
        self.assertEqual(result.stage2_metrics.actions, ActionCounts(4, 3, 1, 0))
        self.assertEqual(result.stage3_metrics.actions, ActionCounts(4, 2, 1, 1))
        self.assertFalse(context.matches_canonical_recorded_start)
        self.assertIs(result.context.human_replay.events, context.human_replay.events)

    def test_stage2_replay_elapsed_is_not_a_performance_metric(self):
        def changed_clock(engine, **kwargs):
            result = run_simple(engine, **kwargs)
            replay = replace(result.replay_data, events=tuple(
                replace(event, elapsed_time=90000 + index) for index, event in enumerate(result.replay_data.events)
            ))
            return replace(result, replay_data=replay)

        with patch("same_board_runner.run_simple", side_effect=changed_clock):
            result = run_same_board_comparison(human_context())
        self.assertEqual(result.human_metrics.replay_elapsed_seconds, 12.5)
        self.assertEqual(result.stage2_result.replay_data.events[-1].elapsed_time, 90003)
        self.assertEqual(result.stage2_metrics.model_c_total_us,
                         result.model_c_evaluation.table[0][0] + 3 * result.model_c_evaluation.table[1][0])

    def test_context_replay_attachment_and_all_retained_outputs_remain_immutable(self):
        context = human_context(with_trace=True)
        before = deepcopy(context)
        result = run_same_board_comparison(context)
        self.assertEqual(context, before)
        self.assertIs(result.context, context)
        self.assertIs(result.context.human_replay.mouse_trace, context.human_replay.mouse_trace)
        for model in (result, result.human_metrics, result.stage2_metrics, result.stage3_metrics,
                      result.human_metrics.actions, result.model_c_evaluation):
            for model_field in fields(model):
                with self.subTest(model=type(model), field=model_field.name), self.assertRaises(FrozenInstanceError):
                    setattr(model, model_field.name, None)
        forbidden = {"time", "speed", "performance", "game_index", "seed", "benchmark_set_id", "engine"}
        for model in (result, result.human_metrics, result.stage2_metrics, result.stage3_metrics):
            self.assertTrue(forbidden.isdisjoint(f.name for f in fields(model)))
        self.assertFalse(hasattr(result.human_metrics, "model_c_total_us"))

    def test_pure_execution_import_without_qt_worker_playback_or_telemetry_records(self):
        script = """
import sys, sqlite3
for name in ('PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'stage3_execution',
             'stage3_execution_worker', 'stage3_execution_job', 'stage3_trace_player',
             'telemetry_model', 'telemetry_repository'):
    sys.modules[name] = None
def forbidden(*args, **kwargs):
    raise AssertionError('database connection')
sqlite3.connect = forbidden
from replay_model import ReplayBoard, ReplayData, ReplayEvent
from same_board_comparison import HumanComparisonContext
from same_board_runner import run_same_board_comparison
context = HumanComparisonContext(ReplayData(ReplayBoard(1, 1, 0, ()),
    (ReplayEvent(0, 0, 0, 'OPEN'),)), declared_full_game_human=True)
result = run_same_board_comparison(context)
assert result.stage2_metrics.outcome.name == result.stage3_metrics.outcome.name == 'WON'
"""
        result = subprocess.run([sys.executable, "-c", script],
                                cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class ComparisonFailureTests(unittest.TestCase):
    def test_requires_admitted_context_before_execution(self):
        with patch("same_board_runner.run_simple") as runner:
            with self.assertRaises(ComparisonExecutionError):
                run_same_board_comparison(human_context().human_replay)
            runner.assert_not_called()

    def test_authentication_failure_prevents_execution(self):
        with patch("stage3_physical.load_timing_table", side_effect=ValueError("corrupt")), \
             patch("same_board_runner.run_simple") as runner:
            with self.assertRaises(ModeledTimeValidationError):
                run_same_board_comparison(human_context())
            runner.assert_not_called()

    def test_runner_failures_propagate_without_fabricated_loss_or_retry(self):
        for target, error in (("run_simple", SimpleRunnerError("failed")), ("run_stage3", RuntimeError("failed"))):
            with self.subTest(target=target), patch(f"same_board_runner.{target}", side_effect=error) as runner:
                with self.assertRaises(type(error)) as caught:
                    run_same_board_comparison(human_context())
                self.assertIs(caught.exception, error)
                self.assertEqual(runner.call_count, 1)

    def test_stage2_guess_pause_rejected(self):
        def pause(engine, **kwargs):
            return replace(run_simple(engine, **kwargs), stop_reason=StopReason.GUESS_REQUIRED)

        with patch("same_board_runner.run_simple", side_effect=pause), patch("same_board_runner.run_stage3") as s3:
            with self.assertRaisesRegex(ComparisonExecutionError, "guess pause"):
                run_same_board_comparison(human_context())
            s3.assert_not_called()

    def test_stage2_replay_layout_and_order_mismatches_rejected(self):
        for corruption in ("layout", "moves", "replay"):
            def corrupt(engine, **kwargs):
                result = run_simple(engine, **kwargs)
                if corruption == "layout":
                    return replace(result, replay_data=replace(result.replay_data, board=ReplayBoard(4, 1, 1, {(2, 0)})))
                if corruption == "moves":
                    return replace(result, moves=tuple(reversed(result.moves)))
                events = (replace(result.replay_data.events[0], action="FLAG"), *result.replay_data.events[1:])
                return replace(result, replay_data=replace(result.replay_data, events=events))

            with self.subTest(corruption=corruption), patch("same_board_runner.run_simple", side_effect=corrupt):
                with self.assertRaises(ComparisonExecutionError):
                    run_same_board_comparison(human_context())

    def test_missing_stage2_observer_trace_rejected(self):
        def drop(engine, *, observer, **kwargs):
            return run_simple(engine, observer=lambda t: observer(t) if t.decision is not None else None, **kwargs)

        with patch("same_board_runner.run_simple", side_effect=drop):
            with self.assertRaisesRegex(ComparisonExecutionError, "counts disagree"):
                run_same_board_comparison(human_context())

    def test_structurally_terminal_but_false_stage2_status_rejected_by_reconstruction(self):
        def corrupt(engine, *, observer, **kwargs):
            def capture(trace):
                observer(replace(trace, status_after=GameStatus.LOST) if trace.status_after == GameStatus.WON else trace)
            result = run_simple(engine, observer=capture, **kwargs)
            return replace(result, status=GameStatus.LOST, stop_reason=StopReason.LOST)

        with patch("same_board_runner.run_simple", side_effect=corrupt):
            with self.assertRaisesRegex(ComparisonExecutionError, "Replay reconstruction"):
                run_same_board_comparison(human_context())

    def test_changed_engine_layout_after_execution_is_rejected(self):
        def corrupt(engine, **kwargs):
            result = run_simple(engine, **kwargs)
            engine.reset_with_mines(4, 1, 1, {(2, 0)})
            return result

        with patch("same_board_runner.run_simple", side_effect=corrupt):
            with self.assertRaisesRegex(ComparisonExecutionError, "engine layout"):
                run_same_board_comparison(human_context())

    def test_changed_installed_layout_before_execution_is_rejected(self):
        original = comparison.MinesweeperEngine.reset_with_mines

        def corrupt(engine, width, height, num_mines, mine_positions):
            return original(engine, width, height, num_mines, {(2, 0)})

        context = human_context()
        with patch.object(comparison.MinesweeperEngine, "reset_with_mines", corrupt), \
             patch("same_board_runner.run_simple") as runner:
            with self.assertRaisesRegex(ComparisonExecutionError, "engine layout"):
                run_same_board_comparison(context)
            runner.assert_not_called()

    def test_stage3_recorded_cost_mismatch_is_an_error(self):
        def corrupt(engine, **kwargs):
            result = run_stage3(engine, **kwargs)
            return replace(result, traces=(replace(result.traces[0], modeled_action_us=result.traces[0].modeled_action_us + 1),
                                           *result.traces[1:]))

        with patch("same_board_runner.run_stage3", side_effect=corrupt):
            with self.assertRaisesRegex(ComparisonExecutionError, "independent evaluation"):
                run_same_board_comparison(human_context())

    def test_stage3_structurally_terminal_but_false_status_rejected_by_reconstruction(self):
        def corrupt(engine, **kwargs):
            result = run_stage3(engine, **kwargs)
            return replace(result, status=GameStatus.LOST, traces=(
                *result.traces[:-1], replace(result.traces[-1], status_after=GameStatus.LOST),
            ))

        with patch("same_board_runner.run_stage3", side_effect=corrupt):
            with self.assertRaisesRegex(ComparisonExecutionError, "fixed-board reconstruction"):
                run_same_board_comparison(human_context())

    def test_fake_first_decision_timing_and_invalid_measurements_rejected(self):
        for value, first in ((0, True), (True, False), (-1, False), (1.5, False)):
            def corrupt(engine, *, observer, **kwargs):
                def capture(trace):
                    selected = (trace.decision is None) == first
                    observer(replace(trace, decision_compute_ns=value) if selected else trace)
                return run_simple(engine, observer=capture, **kwargs)

            with self.subTest(value=value, first=first), patch("same_board_runner.run_simple", side_effect=corrupt):
                with self.assertRaises(ComparisonExecutionError):
                    run_same_board_comparison(human_context())


if __name__ == "__main__":
    unittest.main()
