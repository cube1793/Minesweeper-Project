"""Opt-in runner boundary tests using public observations and real Engine steps."""

import unittest
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from unittest.mock import Mock, patch

import simple_runner
from core_engine import Action, CellState, GameStatus, MinesweeperEngine
from replay_model import SOURCE_ALGORITHM
from replay_player import ReplayPlayer
from replay_recorder import ReplayRecorder
from simple_algorithm import SimpleMove
from simple_decision import DecisionKind, analyze_position
from simple_runner import SimpleActionTrace, SimpleRunnerError, StopReason, run_simple


H = CellState.HIDDEN
F = CellState.FLAGGED


def engine_with_mines(width, height, mines):
    engine = MinesweeperEngine(width, height, len(mines))
    engine.reset_with_mines(width, height, len(mines), mines)
    return engine


class SimpleRunnerInstrumentationTests(unittest.TestCase):
    def assert_initial_open_rejected_without_mutation(self, engine, initial_open):
        before = deepcopy(vars(engine))
        observer = Mock()
        with (
            patch.object(engine, "step", wraps=engine.step) as step,
            patch.object(engine, "get_board_snapshot", wraps=engine.get_board_snapshot) as snapshot,
            patch("simple_runner.analyze_position") as analyze,
            self.assertRaisesRegex(ValueError, "initial_open"),
        ):
            run_simple(engine, initial_open=initial_open, observer=observer)
        step.assert_not_called()
        snapshot.assert_not_called()
        analyze.assert_not_called()
        observer.assert_not_called()
        self.assertEqual(vars(engine), before)

    def test_malformed_initial_open_is_rejected_before_mutation(self):
        for value in (
            (), (0,), (0, 0, 0), 0, 1.5, "00", b"00", {0, 1}, {0: 0, 1: 0},
            (True, 0), (0, False), (False, True), (0.0, 0), (0, "0"),
            (None, 0), ((0, 0), 0), [0], [0, True],
        ):
            with self.subTest(initial_open=value):
                self.assert_initial_open_rejected_without_mutation(
                    MinesweeperEngine(3, 2, 1), value,
                )

    def test_initial_open_bounds_are_validated_before_mutation(self):
        for value in ((-1, 0), (0, -1), (3, 0), (0, 2)):
            with self.subTest(initial_open=value):
                self.assert_initial_open_rejected_without_mutation(
                    engine_with_mines(3, 2, {(1, 0)}), value,
                )

    def test_initial_open_rejects_opened_or_flagged_starts_even_with_hidden_target(self):
        for action in (Action.OPEN, Action.FLAG):
            for target in ((0, 0), (2, 0)):
                with self.subTest(action=action, target=target):
                    engine = engine_with_mines(4, 1, {(1, 0)})
                    engine.step(0, 0, action)
                    self.assertEqual(engine.status, GameStatus.PLAYING)
                    self.assert_initial_open_rejected_without_mutation(engine, target)

    def test_initial_open_rejects_terminal_engines_before_mutation(self):
        for x in (0, 1):
            with self.subTest(x=x):
                engine = engine_with_mines(2, 1, {(1, 0)})
                engine.step(x, 0, Action.OPEN)
                self.assert_initial_open_rejected_without_mutation(engine, (0, 0))

    def test_explicit_initial_open_overrides_fresh_origin_policy_and_bypasses_analysis(self):
        for fresh in (False, True):
            with self.subTest(fresh=fresh):
                engine = (MinesweeperEngine(3, 2, 0) if fresh
                          else engine_with_mines(3, 2, set()))
                traces = []
                with (
                    patch.object(engine, "step", wraps=engine.step) as step,
                    patch("simple_runner.analyze_position") as analyze,
                    patch("simple_runner.perf_counter_ns") as timer,
                ):
                    result = run_simple(engine, initial_open=(2, 1), observer=traces.append)
                step.assert_called_once_with(2, 1, Action.OPEN)
                analyze.assert_not_called()
                timer.assert_not_called()
                self.assertEqual(result.moves, (SimpleMove(Action.OPEN, 2, 1),))
                self.assertEqual(traces, [SimpleActionTrace(
                    result.moves[0], None, None, GameStatus.WON, 6, 0,
                )])
                self.assertTrue(result.started_from_hidden)

    def test_explicit_initial_open_is_consumed_once_before_normal_analysis(self):
        engine = engine_with_mines(4, 1, {(1, 0)})
        traces = []
        with patch("simple_runner.analyze_position", wraps=analyze_position) as analyze:
            result = run_simple(engine, initial_open=(0, 0), observer=traces.append)
        self.assertEqual(result.moves, (
            SimpleMove(Action.OPEN, 0, 0), SimpleMove(Action.FLAG, 1, 0),
            SimpleMove(Action.OPEN, 2, 0), SimpleMove(Action.OPEN, 3, 0),
        ))
        self.assertEqual(analyze.call_count, 3)
        self.assertEqual(analyze.call_args_list[0].args, ([[1, H, H, H]], 1))
        self.assertEqual([trace.move for trace in traces], list(result.moves))
        self.assertIsNone(traces[0].decision)
        self.assertIsNone(traces[0].decision_compute_ns)
        self.assertTrue(all(trace.decision.move == trace.move for trace in traces[1:]))
        self.assertEqual([trace.explicit_flag_delta for trace in traces], [0, 1, 0, 0])
        self.assertEqual([trace.safe_cells_opened_delta for trace in traces], [1, 0, 1, 1])

    def test_implicit_fresh_open_is_observed_once_as_an_untimed_policy_action(self):
        engine = MinesweeperEngine(4, 1, 1)
        traces = []
        with (
            patch("core_engine.random.sample", return_value=[(1, 0)]),
            patch("simple_runner.perf_counter_ns", side_effect=range(6)) as timer,
        ):
            result = run_simple(engine, observer=traces.append)
        self.assertEqual(len(traces), len(result.moves))
        self.assertEqual(traces[0], SimpleActionTrace(
            SimpleMove(Action.OPEN, 0, 0), None, None, GameStatus.PLAYING, 1, 0,
        ))
        self.assertEqual([trace.decision_compute_ns for trace in traces[1:]], [1, 1, 1])
        self.assertEqual(timer.call_count, 6)

    def test_observer_order_and_timer_exclude_all_other_runner_work(self):
        engine = engine_with_mines(4, 1, {(1, 0)})
        recorder = ReplayRecorder(4, 1, 1, SOURCE_ALGORITHM)
        order, traces, decisions = [], [], []
        clock_value = 0
        in_step = False
        original_step = engine.step
        original_observation = engine.get_observation
        original_record = recorder.record_event
        original_capture = recorder.capture_board
        original_deltas = simple_runner._action_effect_deltas
        original_hidden_count = simple_runner._hidden_count

        def work(name, cost=100):
            nonlocal clock_value
            order.append(name)
            clock_value += cost

        def timer():
            order.append("timer")
            return clock_value

        def analyze(observation, num_mines):
            work("analyze", 7)
            decision = analyze_position(observation, num_mines)
            decisions.append(decision)
            return decision

        def step(*args):
            nonlocal in_step
            work("step")
            in_step = True
            try:
                return original_step(*args)
            finally:
                in_step = False

        def observation():
            if not in_step:
                work("observation")
            return original_observation()

        def record(*args):
            work("record")
            return original_record(*args)

        def capture(snapshot):
            work("capture")
            return original_capture(snapshot)

        def deltas(before, after, move):
            work("deltas")
            self.assertEqual(after, original_observation())
            return original_deltas(before, after, move)

        def hidden_count(observation):
            work("check")
            return original_hidden_count(observation)

        def observe(trace):
            work("observe")
            traces.append(trace)
            self.assertEqual(len(recorder.events), len(traces))
            self.assertIsNotNone(recorder.board)
            self.assertEqual(trace.status_after, engine.status)

        with (
            patch("simple_runner.ReplayRecorder", return_value=recorder),
            patch("simple_runner.perf_counter_ns", side_effect=timer),
            patch("simple_runner.analyze_position", side_effect=analyze),
            patch.object(engine, "step", side_effect=step),
            patch.object(engine, "get_observation", side_effect=observation),
            patch.object(recorder, "record_event", side_effect=record),
            patch.object(recorder, "capture_board", side_effect=capture),
            patch("simple_runner._action_effect_deltas", side_effect=deltas),
            patch("simple_runner._hidden_count", side_effect=hidden_count),
        ):
            result = run_simple(engine, initial_open=(0, 0), observer=observe)

        self.assertEqual(order, ["observation", "check"] + [
            "step", "record", "capture", "observation", "deltas", "check", "observe",
        ] + [
            "timer", "analyze", "timer", "step", "record",
            "observation", "deltas", "check", "observe",
        ] * 3)
        self.assertEqual([trace.decision_compute_ns for trace in traces], [None, 7, 7, 7])
        self.assertEqual([trace.move for trace in traces], list(result.moves))
        for trace, decision in zip(traces[1:], decisions):
            self.assertIs(trace.decision, decision)
        self.assertEqual([trace.status_after for trace in traces], [GameStatus.PLAYING] * 3 + [GameStatus.WON])

    def test_effects_are_derived_before_failed_progress_check_but_not_observed(self):
        engine = engine_with_mines(3, 1, {(1, 0)})
        observer = Mock()
        with (
            patch.object(engine, "step"),
            patch("simple_runner._action_effect_deltas", wraps=simple_runner._action_effect_deltas) as deltas,
            self.assertRaisesRegex(SimpleRunnerError, "no progress"),
        ):
            run_simple(engine, initial_open=(0, 0), observer=observer)
        deltas.assert_called_once_with([[H, H, H]], [[H, H, H]], SimpleMove(Action.OPEN, 0, 0))
        observer.assert_not_called()

    def test_step_exception_produces_no_trace(self):
        engine = engine_with_mines(3, 1, {(1, 0)})
        observer = Mock()
        with (
            patch.object(engine, "step", side_effect=RuntimeError("step failed")),
            self.assertRaisesRegex(RuntimeError, "step failed"),
        ):
            run_simple(engine, initial_open=(0, 0), observer=observer)
        observer.assert_not_called()

    def test_none_observer_skips_all_telemetry_work_and_preserves_default_results(self):
        for initial_open in (None, (0, 0)):
            for accept_guesses in (False, True):
                with self.subTest(initial_open=initial_open, accept_guesses=accept_guesses):
                    engine = engine_with_mines(5, 1, {(1, 0), (2, 0)})
                    observed_engine = engine_with_mines(5, 1, {(1, 0), (2, 0)})
                    with (
                        patch("simple_runner.perf_counter_ns", side_effect=AssertionError("unexpected timing")),
                        patch("simple_runner._action_effect_deltas", side_effect=AssertionError("unexpected effects")),
                        patch("simple_runner.SimpleActionTrace", side_effect=AssertionError("unexpected trace")),
                        patch.object(engine, "get_elapsed_time", return_value=0.0),
                    ):
                        result = run_simple(engine, initial_open=initial_open, accept_guesses=accept_guesses)
                    traces = []
                    with patch.object(observed_engine, "get_elapsed_time", return_value=0.0):
                        observed = run_simple(observed_engine, initial_open=initial_open,
                                              accept_guesses=accept_guesses, observer=traces.append)
                    self.assertEqual(result, observed)
                    self.assertEqual(engine.get_observation(), observed_engine.get_observation())
                    self.assertEqual(engine.get_counter_snapshot(), observed_engine.get_counter_snapshot())
                    self.assertEqual(len(traces), len(result.moves))

    def test_guess_policy_without_explicit_initial_open_is_unchanged_with_observer(self):
        for accept_guesses in (False, True):
            with self.subTest(accept_guesses=accept_guesses):
                engine = engine_with_mines(3, 1, {(0, 0)})
                traces = []
                with patch.object(engine, "step", wraps=engine.step) as step:
                    result = run_simple(engine, accept_guesses=accept_guesses, observer=traces.append)
                if accept_guesses:
                    step.assert_called_once_with(0, 0, Action.OPEN)
                    self.assertEqual(len(traces), 1)
                    self.assertEqual(traces[0].decision.kind, DecisionKind.PROBABILITY_GUESS)
                    self.assertEqual(traces[0].status_after, GameStatus.LOST)
                    self.assertEqual(result.stop_reason, StopReason.LOST)
                else:
                    step.assert_not_called()
                    self.assertEqual(traces, [])
                    self.assertEqual(result.stop_reason, StopReason.GUESS_REQUIRED)
                    self.assertEqual(result.pending_decision.kind, DecisionKind.PROBABILITY_GUESS)

    def test_pending_guess_after_executed_moves_gets_no_trace(self):
        engine = engine_with_mines(5, 1, {(1, 0), (2, 0)})
        traces = []
        result = run_simple(engine, initial_open=(0, 0), observer=traces.append)
        self.assertEqual([trace.move for trace in traces], list(result.moves))
        self.assertEqual(len(traces), 2)
        self.assertEqual(result.stop_reason, StopReason.GUESS_REQUIRED)
        self.assertNotIn(result.pending_decision.move, result.moves)
        self.assertTrue(all(trace.status_after == GameStatus.PLAYING for trace in traces))

    def test_observer_exception_propagates_after_execution_without_retry(self):
        engine = engine_with_mines(4, 1, {(1, 0)})
        error = RuntimeError("observer failed")
        observer = Mock(side_effect=error)
        with (
            patch.object(engine, "step", wraps=engine.step) as step,
            self.assertRaises(RuntimeError) as raised,
        ):
            run_simple(engine, initial_open=(0, 0), observer=observer)
        self.assertIs(raised.exception, error)
        observer.assert_called_once()
        step.assert_called_once_with(0, 0, Action.OPEN)
        self.assertEqual(engine.get_observation(), [[1, H, H, H]])

    def test_terminal_engine_gets_no_action_analysis_timing_effects_or_trace(self):
        for x in (0, 1):
            with self.subTest(x=x):
                engine = engine_with_mines(2, 1, {(1, 0)})
                engine.step(x, 0, Action.OPEN)
                observer = Mock()
                with (
                    patch.object(engine, "step") as step,
                    patch("simple_runner.analyze_position") as analyze,
                    patch("simple_runner.perf_counter_ns") as timer,
                    patch("simple_runner._action_effect_deltas") as deltas,
                ):
                    result = run_simple(engine, observer=observer)
                for mock in (step, analyze, timer, deltas, observer):
                    mock.assert_not_called()
                self.assertEqual(result.moves, ())
                self.assertEqual(result.status, engine.status)

    def test_explicit_open_safety_ignores_layout_and_replay_captures_only_after_step(self):
        for mines, status in (({(0, 0)}, GameStatus.WON), ({(2, 0)}, GameStatus.LOST)):
            with self.subTest(mines=mines):
                engine = engine_with_mines(3, 1, mines)
                recorder = ReplayRecorder(3, 1, 1, SOURCE_ALGORITHM)
                original_snapshot = engine.get_board_snapshot
                traces = []

                def snapshot_after_recording():
                    self.assertEqual(len(recorder.events), 1)
                    self.assertEqual(engine.status, status)
                    return original_snapshot()

                with (
                    patch("simple_runner.ReplayRecorder", return_value=recorder),
                    patch.object(engine, "get_board_snapshot", side_effect=snapshot_after_recording) as snapshot,
                    patch("simple_runner.analyze_position") as analyze,
                ):
                    result = run_simple(engine, initial_open=(2, 0), observer=traces.append)
                snapshot.assert_called_once()
                analyze.assert_not_called()
                self.assertEqual(result.moves, (SimpleMove(Action.OPEN, 2, 0),))
                self.assertEqual(result.replay_data.board.mine_positions, mines)
                self.assertEqual(len(traces), 1)
                self.assertIsNone(traces[0].decision)
                self.assertIsNone(traces[0].decision_compute_ns)
                self.assertEqual(traces[0].status_after, status)
                player = ReplayPlayer(result.replay_data)
                self.assertEqual(player.go_to(player.event_count), engine.get_observation())

    def test_safe_reveal_delta_uses_exact_public_transition_definition(self):
        states = [H, F, *range(9), CellState.EXPLODED, CellState.MINE, CellState.FALSE_FLAG]
        for before in states:
            for after in states:
                with self.subTest(before=before, after=after):
                    safe, _ = simple_runner._action_effect_deltas(
                        [[before]], [[after]], SimpleMove(Action.OPEN, 0, 0),
                    )
                    expected = int(before in (H, F) and after in range(9))
                    self.assertEqual(safe, expected)

    def test_win_auto_flags_are_excluded_from_explicit_flag_delta(self):
        engine = engine_with_mines(2, 1, {(1, 0)})
        traces = []
        run_simple(engine, initial_open=(0, 0), observer=traces.append)
        self.assertEqual(engine.count_flags(), 1)
        self.assertEqual(traces, [SimpleActionTrace(
            SimpleMove(Action.OPEN, 0, 0), None, None, GameStatus.WON, 1, 0,
        )])

    def test_flood_counts_flagged_safe_reveal_and_excludes_automatic_unflag(self):
        engine = engine_with_mines(4, 3, {(0, 0)})
        engine.step(0, 0, Action.FLAG)
        engine.step(3, 1, Action.FLAG)
        before = engine.get_observation()
        # Isolate execution effects from the solver's assumed-mine validation.
        decision = analyze_position([[H] * 4 for _ in range(3)], 1)
        decision = replace(decision, move=SimpleMove(Action.OPEN, 3, 0))
        traces = []
        with patch("simple_runner.analyze_position", return_value=decision):
            result = run_simple(engine, accept_guesses=True, observer=traces.append)
        self.assertEqual(result.status, GameStatus.WON)
        self.assertEqual(before[1][3], F)
        self.assertEqual(engine.get_observation()[1][3], 0)
        self.assertEqual(engine.count_flags(), 1)
        self.assertEqual(len(traces), 1)
        self.assertEqual(traces[0].safe_cells_opened_delta, 11)
        self.assertEqual(traces[0].explicit_flag_delta, 0)

    def test_loss_display_states_do_not_count_as_safe_reveals_or_explicit_unflags(self):
        engine = engine_with_mines(5, 2, {(0, 0), (2, 0), (4, 0)})
        engine.step(2, 0, Action.FLAG)
        engine.step(1, 1, Action.FLAG)
        traces = []
        run_simple(engine, accept_guesses=True, observer=traces.append)
        after = engine.get_observation()
        self.assertEqual(after[0][0], CellState.EXPLODED)
        self.assertEqual(after[0][4], CellState.MINE)
        self.assertEqual(after[1][1], CellState.FALSE_FLAG)
        self.assertEqual(len(traces), 1)
        self.assertEqual(traces[0].safe_cells_opened_delta, 0)
        self.assertEqual(traces[0].explicit_flag_delta, 0)

    def test_trace_is_immutable_execution_dto_and_is_not_part_of_run_result(self):
        traces = []
        result = run_simple(engine_with_mines(3, 1, {(0, 0)}),
                            accept_guesses=True, observer=traces.append)
        trace = traces[0]
        self.assertEqual({field.name for field in fields(trace)}, {
            "move", "decision", "decision_compute_ns", "status_after",
            "safe_cells_opened_delta", "explicit_flag_delta",
        })
        for field in fields(trace):
            with self.subTest(field=field.name), self.assertRaises(FrozenInstanceError):
                setattr(trace, field.name, None)
        with self.assertRaises(FrozenInstanceError):
            trace.move.x = 2
        with self.assertRaises(FrozenInstanceError):
            trace.decision.kind = DecisionKind.GLOBAL_CERTAINTY
        self.assertEqual({field.name for field in fields(result)}, {
            "status", "stop_reason", "moves", "replay_data", "pending_decision", "started_from_hidden",
        })


if __name__ == "__main__":
    unittest.main()
