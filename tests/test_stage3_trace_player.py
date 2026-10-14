"""Independent runner observations are the playback oracle, at every prefix."""

import unittest
from contextlib import ExitStack
from dataclasses import replace
from unittest.mock import patch

from benchmark_board import BenchmarkBoard, BenchmarkSetSpec, calculate_board_fingerprint
from core_engine import Action, CellState, GameStatus, MinesweeperEngine
from simple_algorithm import SimpleMove
from stage3_execution import Stage3Execution
from stage3_runner import Stage3ActionTrace, Stage3RunResult, run_stage3
from stage3_trace_player import Stage3TracePlayer


H, F = CellState.HIDDEN, CellState.FLAGGED


def captured_execution(width=4, height=1, mines=frozenset({(1, 0)})):
    # These fixed layouts also exercise the frozen runner's existing fixtures.
    spec = BenchmarkSetSpec("TRACE_TEST_V1", width, height, len(mines), 0, 0, "V1", "game_index")
    board = BenchmarkBoard(0, 0, mines, calculate_board_fingerprint(width, height, len(mines), mines))
    engine = MinesweeperEngine(width, height, len(mines))
    engine.reset_with_mines(width, height, len(mines), mines)
    prefixes = [(engine.get_observation(), engine.status)]

    def observe(trace):
        prefixes.append((engine.get_observation(), engine.status))

    result = run_stage3(engine, observer=observe)
    return Stage3Execution(spec, board, result), prefixes


class Stage3TracePlayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sequence, cls.prefixes = captured_execution()
        cls.flood, cls.flood_prefixes = captured_execution(3, 1, frozenset({(2, 0)}))
        cls.loss, cls.loss_prefixes = captured_execution(5, 1, frozenset({(1, 0), (2, 0)}))
        cls.first_loss, cls.first_loss_prefixes = captured_execution(3, 1, frozenset({(0, 0), (2, 0)}))
        cls.suffix, cls.suffix_prefixes = captured_execution(
            6, 4, frozenset({(1, 2), (2, 1), (4, 0), (4, 1), (4, 2)}),
        )

    def state(self, player):
        return (
            player.current_index, player.current_trace, player.current_cursor,
            player.cumulative_modeled_us, player.status, player.get_observation(),
        )

    def assert_prefix(self, player, index, prefixes):
        traces = player.execution.result.traces
        self.assertEqual(player.current_index, index)
        self.assertEqual((player.get_observation(), player.status), prefixes[index])
        self.assertIs(player.current_trace, None if index == 0 else traces[index - 1])
        expected_cursor = (0, 0) if index == 0 else (traces[index - 1].move.x, traces[index - 1].move.y)
        self.assertEqual(player.current_cursor, expected_cursor)
        self.assertEqual(player.cumulative_modeled_us, sum(trace.modeled_action_us for trace in traces[:index]))
        self.assertIs(type(player.cumulative_modeled_us), int)

    def test_initial_index_is_the_all_hidden_fixed_board(self):
        player = Stage3TracePlayer(self.sequence)
        self.assertIs(player.execution, self.sequence)
        self.assertEqual(player.step_count, 4)
        self.assert_prefix(player, 0, self.prefixes)
        self.assertEqual(player.get_observation(), [[H, H, H, H]])
        self.assertEqual(player.status, GameStatus.PLAYING)

    def test_next_previous_and_boundaries(self):
        player = Stage3TracePlayer(self.sequence)
        self.assertFalse(player.previous())
        for index in range(1, player.step_count + 1):
            self.assertTrue(player.next())
            self.assert_prefix(player, index, self.prefixes)
        self.assertFalse(player.next())
        for index in range(player.step_count - 1, -1, -1):
            self.assertTrue(player.previous())
            self.assert_prefix(player, index, self.prefixes)
        self.assertFalse(player.previous())

    def test_every_prefix_matches_independent_runner_capture_in_any_seek_order(self):
        for execution, prefixes in (
            (self.sequence, self.prefixes), (self.flood, self.flood_prefixes),
            (self.loss, self.loss_prefixes), (self.first_loss, self.first_loss_prefixes),
            (self.suffix, self.suffix_prefixes),
        ):
            player = Stage3TracePlayer(execution)
            count = player.step_count
            orders = (
                list(range(count + 1)), list(range(count, -1, -1)),
                [count, 0, count // 2, 1, count, 0, count - 1, count],
            )
            for order in orders:
                for index in order:
                    with self.subTest(spec=execution.spec, index=index, order=order):
                        observation = player.go_to(index)
                        self.assertEqual(observation, prefixes[index][0])
                        self.assert_prefix(player, index, prefixes)
            self.assertEqual(player.status, execution.result.status)

    def test_invalid_seek_leaves_every_public_state_value_unchanged(self):
        player = Stage3TracePlayer(self.sequence)
        for start in (0, 2, player.step_count):
            player.go_to(start)
            before = self.state(player)
            for invalid in (-1, player.step_count + 1, True, False, 0.0, 1.5, "1", None, [], {}):
                with self.subTest(start=start, invalid=invalid):
                    with self.assertRaises(ValueError):
                        player.go_to(invalid)
                    self.assertEqual(self.state(player), before)
                    self.assertIs(player.current_trace, before[1])

    def test_open_flag_open_chord_has_only_four_physical_actions(self):
        self.assertEqual(self.sequence.result.moves, (
            SimpleMove(Action.OPEN, 0, 0), SimpleMove(Action.FLAG, 1, 0),
            SimpleMove(Action.OPEN, 2, 0), SimpleMove(Action.CHORD, 2, 0),
        ))
        player = Stage3TracePlayer(self.sequence)
        for index, observation in enumerate((
            [[H, H, H, H]], [[1, H, H, H]], [[1, F, H, H]],
            [[1, F, 1, H]], [[1, F, 1, 0]],
        )):
            self.assertEqual(player.go_to(index), observation)
        self.assertEqual(player.status, GameStatus.WON)
        self.assertEqual(player.step_count, 4)

    def test_flood_and_automatic_win_flags_are_engine_effects(self):
        player = Stage3TracePlayer(self.flood)
        self.assertEqual(player.step_count, 1)
        self.assertEqual(player.go_to(1), [[0, 1, F]])
        self.assertEqual(player.status, GameStatus.WON)
        self.assertEqual(player.current_trace.move.action, Action.OPEN)
        self.assertEqual(player.current_trace.explicit_flag_delta, 0)
        self.assertEqual(player.cumulative_modeled_us, self.flood.result.total_modeled_us)

    def test_loss_reveals_unopened_mines_and_explosion(self):
        player = Stage3TracePlayer(self.loss)
        observation = player.go_to(player.step_count)
        self.assertEqual(player.status, GameStatus.LOST)
        self.assertEqual(observation[0][1], CellState.FLAGGED)
        self.assertEqual(observation[0][2], CellState.EXPLODED)
        self.assertEqual(player.cumulative_modeled_us, self.loss.result.total_modeled_us)
        first_loss = Stage3TracePlayer(self.first_loss)
        self.assertEqual(first_loss.go_to(1), [[CellState.EXPLODED, H, CellState.MINE]])
        self.assertEqual(first_loss.status, GameStatus.LOST)

    def test_false_flags_are_reconstructed_by_the_engine(self):
        # A consumer-only recorded stream: no Stage-3 inference is claimed for
        # this deliberately incorrect flag. Playback must not infer flag safety.
        engine = MinesweeperEngine(4, 1, 1)
        engine.reset_with_mines(4, 1, 1, {(1, 0)})
        traces, cursor = [], (0, 0)
        for move in (SimpleMove(Action.OPEN, 0, 0), SimpleMove(Action.FLAG, 2, 0), SimpleMove(Action.OPEN, 1, 0)):
            engine.step(move.x, move.y, move.action)
            traces.append(Stage3ActionTrace(move, None, None, cursor, 7, engine.status, 0, 0))
            cursor = (move.x, move.y)
        execution = replace(self.sequence, result=Stage3RunResult(engine.status, traces))
        player = Stage3TracePlayer(execution)
        self.assertEqual(player.go_to(3), engine.get_observation())
        self.assertEqual(player.get_observation(), [[1, CellState.EXPLODED, CellState.FALSE_FLAG, H]])

    def test_cursor_uses_executed_target_and_preserves_cursor_before(self):
        player = Stage3TracePlayer(self.sequence)
        original_origins = tuple(trace.cursor_before for trace in self.sequence.result.traces)
        self.assertEqual(player.current_cursor, (0, 0))
        for index, trace in enumerate(self.sequence.result.traces, start=1):
            player.go_to(index)
            self.assertIs(player.current_trace, trace)
            self.assertEqual(player.current_cursor, (trace.move.x, trace.move.y))
            self.assertEqual(trace.cursor_before, original_origins[index - 1])
        player.go_to(0)
        player.go_to(player.step_count)
        self.assertEqual(tuple(trace.cursor_before for trace in self.sequence.result.traces), original_origins)

    def test_modeled_time_uses_recorded_integer_prefixes_without_rounding(self):
        costs = (2**60 + 1, 3, 2**60 + 7, 11)
        result = replace(self.sequence.result, traces=tuple(
            replace(trace, modeled_action_us=cost)
            for trace, cost in zip(self.sequence.result.traces, costs)
        ))
        player = Stage3TracePlayer(replace(self.sequence, result=result))
        for index in (0, 1, 2, 4, 3, 1, 4, 0, 4):
            player.go_to(index)
            self.assertIs(type(player.cumulative_modeled_us), int)
            self.assertEqual(player.cumulative_modeled_us, sum(costs[:index]))
        self.assertEqual(player.cumulative_modeled_us, result.total_modeled_us)

    def test_playback_never_runs_inference_generation_or_physical_cost_calculation(self):
        forbidden = (
            "stage3_execution.run_stage3", "stage3_runner.run_stage3",
            "stage3_runner.plan_position", "stage3_planner.plan_position",
            "stage3_planner.analyze_position", "simple_decision.analyze_position",
            "simple_decision.calculate_probabilities", "simple_probability.calculate_probabilities",
            "simple_decision.choose_probability_move", "simple_probability.choose_probability_move",
            "stage3_execution.generate_board", "benchmark_board.generate_board",
            "stage3_physical.action_cost", "stage3_physical.load_timing_table",
        )
        with ExitStack() as stack:
            mocks = [stack.enter_context(patch(name, side_effect=AssertionError(name))) for name in forbidden]
            player = Stage3TracePlayer(self.suffix)
            for index in (player.step_count, 0, 6, 2, player.step_count):
                player.go_to(index)
            player.previous()
            player.next()
            for mocked in mocks:
                mocked.assert_not_called()

    def test_terminal_win_and_loss_do_not_accept_an_extra_action(self):
        for execution in (self.sequence, self.flood, self.loss, self.first_loss):
            with self.subTest(status=execution.result.status, steps=len(execution.result.traces)):
                player = Stage3TracePlayer(execution)
                player.go_to(player.step_count)
                terminal = self.state(player)
                with patch.object(MinesweeperEngine, "step", side_effect=AssertionError("extra action")):
                    self.assertFalse(player.next())
                    self.assertEqual(player.go_to(player.step_count), terminal[-1])
                    self.assertEqual(self.state(player), terminal)

    def test_obsolete_planned_suffix_is_never_executed(self):
        execution = self.suffix
        setup = execution.result.traces[4]
        self.assertEqual(setup.decision.plan.actions, (
            SimpleMove(Action.FLAG, 2, 1), SimpleMove(Action.FLAG, 1, 2),
            SimpleMove(Action.CHORD, 2, 2),
        ))
        self.assertEqual(execution.result.traces[5].move, SimpleMove(Action.OPEN, 2, 0))
        applied = []
        real_step = MinesweeperEngine.step

        def step(engine, x, y, action):
            applied.append(SimpleMove(action, x, y))
            return real_step(engine, x, y, action)

        player = Stage3TracePlayer(execution)
        with patch.object(MinesweeperEngine, "step", new=step):
            player.go_to(6)
        self.assertEqual(tuple(applied), execution.result.moves[:6])
        self.assert_prefix(player, 6, self.suffix_prefixes)
        self.assertEqual(player.get_observation()[2][1], H)

    def test_players_and_returned_observations_are_independent(self):
        first, second = Stage3TracePlayer(self.sequence), Stage3TracePlayer(self.sequence)
        first.go_to(first.step_count)
        self.assert_prefix(second, 0, self.prefixes)
        observation = first.get_observation()
        observation[0][0] = 999
        self.assert_prefix(first, first.step_count, self.prefixes)

    def test_trace_status_mismatch_fails_without_publishing_partial_seek(self):
        traces = list(self.sequence.result.traces)
        traces[2] = replace(traces[2], status_after=GameStatus.LOST)
        execution = replace(self.sequence, result=replace(self.sequence.result, traces=traces))
        player = Stage3TracePlayer(execution)
        player.go_to(1)
        before = self.state(player)
        with self.assertRaisesRegex(ValueError, "Trace 3 status_after"):
            player.go_to(3)
        self.assertEqual(self.state(player), before)
        player.go_to(2)
        self.assert_prefix(player, 2, self.prefixes)

    def test_final_status_mismatch_fails_without_publishing_terminal_state(self):
        execution = replace(self.sequence, result=replace(self.sequence.result, status=GameStatus.LOST))
        player = Stage3TracePlayer(execution)
        player.go_to(2)
        before = self.state(player)
        with self.assertRaisesRegex(ValueError, "result.status"):
            player.go_to(player.step_count)
        self.assertEqual(self.state(player), before)

    def test_trace_after_terminal_is_rejected_before_engine_step(self):
        result = replace(self.flood.result, traces=self.flood.result.traces * 2)
        player = Stage3TracePlayer(replace(self.flood, result=result))
        before, applied = self.state(player), []
        real_step = MinesweeperEngine.step

        def step(engine, x, y, action):
            self.assertEqual(engine.status, GameStatus.PLAYING)
            applied.append((x, y, action))
            return real_step(engine, x, y, action)

        with patch.object(MinesweeperEngine, "step", new=step):
            with self.assertRaisesRegex(ValueError, "follows a terminal board"):
                player.go_to(2)
        self.assertEqual(len(applied), 1)
        self.assertEqual(self.state(player), before)

    def test_noninteger_or_negative_modeled_cost_fails_without_state_change(self):
        for invalid in (True, False, -1, 0.5, "1", None):
            with self.subTest(cost=invalid):
                result = replace(self.flood.result, traces=(
                    replace(self.flood.result.traces[0], modeled_action_us=invalid),
                ))
                player = Stage3TracePlayer(replace(self.flood, result=result))
                before = self.state(player)
                with self.assertRaisesRegex(ValueError, "modeled_action_us"):
                    player.next()
                self.assertEqual(self.state(player), before)

    def test_empty_playing_stream_has_only_index_zero(self):
        execution = replace(self.sequence, result=Stage3RunResult(GameStatus.PLAYING, ()))
        player = Stage3TracePlayer(execution)
        self.assertEqual(player.step_count, 0)
        self.assert_prefix(player, 0, self.prefixes)
        self.assertFalse(player.next())
        self.assertFalse(player.previous())
        self.assertEqual(player.go_to(0), self.prefixes[0][0])
        with self.assertRaises(ValueError):
            player.go_to(1)

    def test_empty_terminal_result_cannot_reconstruct_a_terminal_board(self):
        for status in (GameStatus.WON, GameStatus.LOST):
            with self.subTest(status=status):
                execution = replace(self.sequence, result=Stage3RunResult(status, ()))
                with self.assertRaisesRegex(ValueError, "Empty trace stream"):
                    Stage3TracePlayer(execution)


if __name__ == "__main__":
    unittest.main()
