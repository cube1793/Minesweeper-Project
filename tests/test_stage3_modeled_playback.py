"""Deterministic modeled-time contracts; fake clocks never sleep."""

import unittest
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from unittest.mock import patch

from benchmark_board import BenchmarkBoard, BenchmarkSetSpec, calculate_board_fingerprint
from core_engine import Action, GameStatus, MinesweeperEngine
from simple_algorithm import SimpleMove
from stage3_execution import Stage3Execution, run_expert_stage3_execution
from stage3_modeled_playback import Stage3ModeledPlayback
from stage3_runner import Stage3ActionTrace, Stage3RunResult
from stage3_trace_player import Stage3TracePlayer


class FakeClock:
    def __init__(self):
        self.now_ns = 0

    def __call__(self):
        return self.now_ns

    def advance(self, nanoseconds):
        self.now_ns += nanoseconds


def recorded_execution(durations=(10, 20, 30, 40)):
    """A fixed OPEN/FLAG/OPEN/CHORD win, independent of planning and Model C."""
    mines = frozenset({(1, 0)})
    spec = BenchmarkSetSpec("MODELED_TEST_V1", 4, 1, 1, 0, 0, "V1", "game_index")
    board = BenchmarkBoard(0, 0, mines, calculate_board_fingerprint(4, 1, 1, mines))
    moves = (
        SimpleMove(Action.OPEN, 0, 0), SimpleMove(Action.FLAG, 1, 0),
        SimpleMove(Action.OPEN, 2, 0), SimpleMove(Action.CHORD, 2, 0),
    )
    traces = tuple(Stage3ActionTrace(
        move=move, decision=None, decision_compute_ns=None,
        cursor_before=(0, 0) if index == 0 else (moves[index - 1].x, moves[index - 1].y),
        modeled_action_us=durations[index],
        status_after=GameStatus.WON if index == 3 else GameStatus.PLAYING,
        safe_cells_opened_delta=0 if index == 1 else 1,
        explicit_flag_delta=int(index == 1),
    ) for index, move in enumerate(moves))
    return Stage3Execution(spec, board, Stage3RunResult(GameStatus.WON, traces))


def make_playback(durations=(10, 20, 30, 40)):
    player = Stage3TracePlayer(recorded_execution(durations))
    clock = FakeClock()
    return player, clock, Stage3ModeledPlayback(player, clock=clock)


def player_state(player):
    return (
        player.current_index, player.get_observation(), player.status,
        player.current_cursor, player.current_trace, player.cumulative_modeled_us,
    )


class Stage3ModeledPlaybackTests(unittest.TestCase):
    def setUp(self):
        self.player, self.clock, self.playback = make_playback()

    def test_initial_state_and_queries_do_not_sample_time(self):
        playback = Stage3ModeledPlayback(
            self.player, clock=lambda: self.fail("A query sampled wall time"),
        )
        self.assertEqual(self.player.current_index, 0)
        self.assertFalse(playback.running)
        self.assertEqual(playback.speed, 1)
        self.assertEqual(playback.partial_modeled_us, 0)
        self.assertEqual(playback.progress, 0)
        self.assertIs(playback.pending_trace, self.player.execution.result.traces[0])
        self.assertEqual(playback.pending_duration_us, 10)
        for name in ("running", "speed", "pending_trace", "pending_duration_us",
                     "partial_modeled_us", "progress"):
            with self.subTest(name=name), self.assertRaises(AttributeError):
                setattr(playback, name, None)
        playback.pause()
        playback.update()
        self.assertEqual(self.player.current_index, 0)

    def test_play_starts_at_current_committed_index_without_rewinding(self):
        self.player.go_to(2)
        before = player_state(self.player)
        self.clock.advance(123456789)
        self.playback.play()
        self.assertTrue(self.playback.running)
        self.assertEqual(player_state(self.player), before)
        self.assertEqual(self.playback.partial_modeled_us, 0)
        self.assertIs(self.playback.pending_trace, self.player.execution.result.traces[2])

    def test_partial_interval_leaves_committed_state_unchanged(self):
        before = player_state(self.player)
        self.playback.play()
        self.clock.advance(3501)
        self.playback.update()
        self.assertEqual(player_state(self.player), before)
        self.assertEqual(self.playback.partial_modeled_us, Fraction(3501, 1000))
        self.assertEqual(self.playback.progress, Fraction(3501, 10000))

    def test_exact_boundary_applies_once_even_at_repeated_timestamp(self):
        self.playback.play()
        self.clock.advance(10000)
        self.playback.update()
        oracle = Stage3TracePlayer(self.player.execution)
        oracle.go_to(1)
        self.assertEqual(player_state(self.player), player_state(oracle))
        self.assertEqual(self.playback.partial_modeled_us, 0)
        self.assertEqual(self.playback.progress, 0)
        self.assertIs(self.playback.pending_trace, self.player.execution.result.traces[1])
        with patch.object(MinesweeperEngine, "step", side_effect=AssertionError("Duplicate action")):
            self.playback.update()
        self.assertEqual(player_state(self.player), player_state(oracle))

    def test_boundary_preserves_fractional_leftover(self):
        self.playback.play()
        self.clock.advance(12501)
        self.playback.update()
        self.assertEqual(self.player.current_index, 1)
        self.assertEqual(self.playback.partial_modeled_us, Fraction(2501, 1000))
        self.assertEqual(self.playback.progress, Fraction(2501, 20000))
        self.assertEqual(self.player.cumulative_modeled_us, 10)

    def test_late_update_applies_every_crossed_action_in_order(self):
        applied = []
        real_step = MinesweeperEngine.step

        def step(engine, x, y, action):
            applied.append(SimpleMove(action, x, y))
            return real_step(engine, x, y, action)

        self.playback.play()
        with patch.object(MinesweeperEngine, "step", new=step):
            self.clock.advance(65000)
            self.playback.update()
            self.assertEqual(tuple(applied), self.player.execution.result.moves[:3])
            self.assertEqual(self.player.current_index, 3)
            self.assertEqual(self.playback.partial_modeled_us, 5)
            self.assertEqual(self.playback.progress, Fraction(1, 8))
            self.clock.advance(35000)
            self.playback.update()
        self.assertEqual(tuple(applied), self.player.execution.result.moves)
        self.assertEqual(self.player.cumulative_modeled_us, 100)
        self.assertFalse(self.playback.running)

    def test_final_boundary_and_excess_time_stop_without_wraparound(self):
        for elapsed_ns in (100000, 1000000000):
            with self.subTest(elapsed_ns=elapsed_ns):
                player, clock, playback = make_playback()
                playback.play()
                clock.advance(elapsed_ns)
                playback.update()
                self.assertEqual(player.current_index, 4)
                self.assertEqual(player.status, GameStatus.WON)
                self.assertFalse(playback.running)
                self.assertIsNone(playback.pending_trace)
                self.assertIsNone(playback.pending_duration_us)
                self.assertEqual((playback.partial_modeled_us, playback.progress), (0, 0))
                terminal = player_state(player)
                clock.now_ns = -1  # Terminal operations must not even sample time.
                playback.update()
                playback.play()
                playback.pause()
                self.assertEqual(player_state(player), terminal)
                self.assertFalse(playback.running)

    def test_constructing_at_final_or_empty_trace_is_inert(self):
        empty = replace(self.player.execution, result=Stage3RunResult(GameStatus.PLAYING, ()))
        self.player.go_to(4)
        for player in (self.player, Stage3TracePlayer(empty)):
            with self.subTest(step_count=player.step_count):
                playback = Stage3ModeledPlayback(player, clock=lambda: self.fail("Terminal clock read"))
                playback.play()
                playback.update()
                self.assertIsNone(playback.pending_trace)
                self.assertFalse(playback.running)
                self.assertEqual(playback.progress, 0)

    def test_same_cell_positive_duration_advances_only_time(self):
        player, clock, playback = make_playback((126005, 7, 11, 13))
        trace = playback.pending_trace
        self.assertEqual(trace.cursor_before, (trace.move.x, trace.move.y))
        playback.play()
        clock.advance(63002500)
        playback.update()
        self.assertEqual(playback.progress, Fraction(1, 2))
        self.assertEqual(player.current_index, 0)
        self.assertEqual(player.current_cursor, (0, 0))
        clock.advance(63002500)
        playback.update()
        self.assertEqual(player.current_index, 1)
        self.assertEqual(player.current_cursor, (0, 0))
        self.assertEqual(player.cumulative_modeled_us, 126005)

    def test_leading_and_trailing_zero_duration_actions_commit_immediately(self):
        player, clock, playback = make_playback((0, 0, 10, 0))
        self.assertEqual(playback.progress, 0)
        self.assertEqual(player.current_index, 0)  # Construction is paused.
        playback.play()
        self.assertEqual(player.current_index, 2)
        self.assertEqual(playback.partial_modeled_us, 0)
        clock.advance(10000)
        playback.update()
        self.assertEqual(player.current_index, 4)
        self.assertEqual(player.cumulative_modeled_us, 10)
        self.assertFalse(playback.running)

    def test_all_zero_duration_actions_finish_on_play(self):
        player, _, playback = make_playback((0, 0, 0, 0))
        playback.play()
        self.assertEqual(player.current_index, 4)
        self.assertEqual(player.status, GameStatus.WON)
        self.assertEqual(player.cumulative_modeled_us, 0)
        self.assertEqual(playback.progress, 0)
        self.assertFalse(playback.running)

    def test_pause_accounts_for_elapsed_boundaries_then_freezes(self):
        self.playback.play()
        self.clock.advance(35000)
        self.playback.pause()
        self.assertEqual(self.player.current_index, 2)
        self.assertEqual(self.playback.partial_modeled_us, 5)
        self.assertFalse(self.playback.running)
        frozen = player_state(self.player)
        self.clock.advance(1000000000)
        self.playback.update()
        self.playback.pause()
        self.assertEqual(player_state(self.player), frozen)
        self.assertEqual(self.playback.partial_modeled_us, 5)

    def test_resume_excludes_paused_wall_time_without_jump(self):
        self.playback.play()
        self.clock.advance(3501)
        self.playback.pause()
        frozen = self.playback.partial_modeled_us
        self.clock.advance(999999999)
        self.playback.play()
        self.assertEqual(self.playback.partial_modeled_us, frozen)
        self.playback.update()
        self.assertEqual(self.playback.partial_modeled_us, frozen)
        self.clock.advance(2499)
        self.playback.update()
        self.assertEqual(self.playback.partial_modeled_us, 6)
        self.assertEqual(self.player.current_index, 0)

    def test_repeated_play_does_not_reset_running_anchor(self):
        self.playback.play()
        self.clock.advance(3500)
        self.playback.play()
        self.clock.advance(2500)
        self.playback.update()
        self.assertEqual(self.playback.partial_modeled_us, 6)

    def test_speed_change_accounts_old_rate_and_boundaries_before_new_rate(self):
        self.playback.play()
        self.clock.advance(12500)
        self.playback.set_speed(2)
        self.assertEqual(self.player.current_index, 1)
        self.assertEqual(self.playback.partial_modeled_us, Fraction(5, 2))
        self.assertEqual(self.playback.speed, 2)
        self.clock.advance(3000)
        self.playback.update()
        self.assertEqual(self.playback.partial_modeled_us, Fraction(17, 2))
        self.assertEqual(self.player.cumulative_modeled_us, 10)

    def test_speed_change_while_paused_changes_only_future_rate(self):
        self.playback.play()
        self.clock.advance(3500)
        self.playback.pause()
        before = player_state(self.player)
        self.clock.advance(1000000000)
        self.playback.set_speed(8)
        self.assertEqual(player_state(self.player), before)
        self.assertEqual(self.playback.partial_modeled_us, Fraction(7, 2))
        self.assertFalse(self.playback.running)
        self.playback.play()
        self.clock.advance(500)
        self.playback.update()
        self.assertEqual(self.playback.partial_modeled_us, Fraction(15, 2))

    def test_all_six_supported_speeds_scale_elapsed_time_exactly(self):
        for speed in (0.25, 0.5, 1, 2, 4, 8):
            with self.subTest(speed=speed):
                player, clock, playback = make_playback()
                playback.set_speed(speed)
                playback.play()
                clock.advance(1001)
                playback.update()
                self.assertEqual(playback.partial_modeled_us, Fraction(1001, 1000) * Fraction(speed))
                self.assertEqual(player.current_index, 0)

    def test_unsupported_speed_is_rejected_before_any_time_or_state_change(self):
        self.playback.play()
        self.clock.advance(5000)
        before = player_state(self.player)
        for speed in (True, False, None, "2", -1, 0, 1.5, 16, float("nan"), float("inf")):
            with self.subTest(speed=speed), self.assertRaisesRegex(ValueError, "Playback speed"):
                self.playback.set_speed(speed)
            self.assertEqual(self.playback.speed, 1)
            self.assertEqual(self.playback.partial_modeled_us, 0)
            self.assertEqual(player_state(self.player), before)
            self.assertTrue(self.playback.running)
        self.playback.update()
        self.assertEqual(self.playback.partial_modeled_us, 5)

    def test_cancel_discards_sampled_and_unsampled_time_without_navigation(self):
        self.playback.play()
        self.clock.advance(12500)
        self.playback.update()
        before = player_state(self.player)
        self.clock.advance(1000000000)
        self.playback.cancel_partial()
        self.assertEqual(player_state(self.player), before)
        self.assertFalse(self.playback.running)
        self.assertEqual(self.playback.partial_modeled_us, 0)
        self.playback.cancel_partial()
        self.playback.play()
        self.playback.update()
        self.assertEqual(player_state(self.player), before)
        self.assertEqual(self.playback.partial_modeled_us, 0)

    def test_navigation_after_cancel_uses_existing_integer_player_semantics(self):
        for navigation, expected in (("next", 2), ("previous", 0), ("first", 0), ("last", 4)):
            with self.subTest(navigation=navigation):
                player, clock, playback = make_playback()
                playback.play()
                clock.advance(12500)
                playback.update()
                playback.cancel_partial()
                if navigation == "first":
                    player.go_to(0)
                elif navigation == "last":
                    player.go_to(4)
                else:
                    getattr(player, navigation)()
                self.assertEqual(player.current_index, expected)
                self.assertEqual(playback.partial_modeled_us, 0)
                self.assertFalse(playback.running)
                pending = None if expected == 4 else player.execution.result.traces[expected]
                self.assertIs(playback.pending_trace, pending)
                playback.play()
                playback.update()
                self.assertEqual(player.current_index, expected)

    def test_backwards_clock_stops_and_preserves_last_sampled_position(self):
        for operation in ("update", "pause", "speed", "resume"):
            with self.subTest(operation=operation):
                player, clock, playback = make_playback()
                playback.play()
                clock.advance(3500)
                playback.update()
                if operation == "resume":
                    playback.pause()
                before = player_state(player)
                clock.now_ns = 3499
                with self.assertRaisesRegex(ValueError, "backwards"):
                    if operation == "speed":
                        playback.set_speed(8)
                    elif operation == "resume":
                        playback.play()
                    else:
                        getattr(playback, operation)()
                self.assertEqual(player_state(player), before)
                self.assertEqual(playback.partial_modeled_us, Fraction(7, 2))
                self.assertEqual(playback.speed, 1)
                self.assertFalse(playback.running)
                playback.update()
                self.assertEqual(player_state(player), before)

    def test_invalid_clock_values_fail_closed(self):
        for invalid in (True, 1.5, None):
            with self.subTest(invalid=invalid):
                player, clock, playback = make_playback()
                playback.play()
                clock.advance(1000)
                playback.update()
                before = player_state(player)
                clock.now_ns = invalid
                with self.assertRaisesRegex(ValueError, "integer nanoseconds"):
                    playback.update()
                self.assertEqual(player_state(player), before)
                self.assertEqual(playback.partial_modeled_us, 1)
                self.assertFalse(playback.running)

    def test_clock_exception_propagates_and_stops_without_advancing(self):
        values = iter((0, 1000))

        def clock():
            try:
                return next(values)
            except StopIteration:
                raise RuntimeError("Clock unavailable")

        playback = Stage3ModeledPlayback(self.player, clock=clock)
        playback.play()
        playback.update()
        before = player_state(self.player)
        with self.assertRaisesRegex(RuntimeError, "Clock unavailable"):
            playback.update()
        self.assertEqual(player_state(self.player), before)
        self.assertEqual(playback.partial_modeled_us, 1)
        self.assertFalse(playback.running)

    def test_player_failure_stops_at_failed_boundary_and_discards_excess_time(self):
        real_step = MinesweeperEngine.step
        attempted = []

        def fail_after_step(engine, x, y, action):
            attempted.append(SimpleMove(action, x, y))
            result = real_step(engine, x, y, action)
            if action == Action.FLAG:
                raise RuntimeError("Injected boundary failure")
            return result

        self.playback.play()
        self.clock.advance(1000000)
        with patch.object(MinesweeperEngine, "step", new=fail_after_step):
            with self.assertRaisesRegex(RuntimeError, "Injected boundary failure"):
                self.playback.update()
            self.playback.update()  # A stopped controller must not silently retry.
        oracle = Stage3TracePlayer(self.player.execution)
        oracle.go_to(1)
        self.assertEqual(player_state(self.player), player_state(oracle))
        self.assertEqual(tuple(attempted), self.player.execution.result.moves[:2])
        self.assertEqual(self.playback.partial_modeled_us, 20)
        self.assertEqual(self.playback.progress, 1)
        self.assertFalse(self.playback.running)
        self.assertIs(self.playback.pending_trace, self.player.execution.result.traces[1])
        self.playback.play()  # Explicit retry commits only the already-due action.
        self.assertEqual(self.player.current_index, 2)
        self.assertEqual(self.playback.partial_modeled_us, 0)
        self.playback.update()
        self.assertEqual(self.player.current_index, 2)

    def test_zero_duration_player_failure_stops_without_looping(self):
        player, _, playback = make_playback((0, 0, 10, 20))
        with patch.object(MinesweeperEngine, "step", side_effect=RuntimeError("Zero failure")):
            with self.assertRaisesRegex(RuntimeError, "Zero failure"):
                playback.play()
        self.assertEqual(player.current_index, 0)
        self.assertEqual(playback.partial_modeled_us, 0)
        self.assertEqual(playback.progress, 0)
        self.assertFalse(playback.running)

    def test_invalid_recorded_durations_cannot_move_timeline_backwards(self):
        for duration in (-1, True, 0.5):
            with self.subTest(duration=duration):
                player, _, playback = make_playback((duration, 20, 30, 40))
                before = player_state(player)
                with self.assertRaisesRegex(ValueError, "nonnegative integer"):
                    playback.play()
                self.assertEqual(player_state(player), before)
                self.assertEqual(playback.partial_modeled_us, 0)
                self.assertFalse(playback.running)

    def test_awkward_durations_and_rate_changes_never_round_partial_time(self):
        large = 2**60 + 1
        player, clock, playback = make_playback((126005, 17, large, 19))
        playback.set_speed(Fraction(1, 4))
        playback.play()
        for _ in range(7):
            clock.advance(1)
            playback.update()
        self.assertEqual(playback.partial_modeled_us, Fraction(7, 4000))
        clock.advance(2)
        playback.set_speed(0.5)
        self.assertEqual(playback.partial_modeled_us, Fraction(9, 4000))
        clock.advance(7)
        playback.pause()
        self.assertEqual(playback.partial_modeled_us, Fraction(23, 4000))
        clock.advance(10**18)
        playback.set_speed(8)
        playback.play()
        clock.advance(11)
        playback.update()
        self.assertEqual(playback.partial_modeled_us, Fraction(3, 32))
        playback.set_speed(0.25)
        clock.advance(504019625)  # Exactly the remaining first duration at 0.25x.
        playback.update()
        self.assertEqual((player.current_index, playback.partial_modeled_us), (1, 0))
        playback.set_speed(0.5)
        clock.advance(34000)
        playback.update()
        self.assertEqual((player.current_index, playback.partial_modeled_us), (2, 0))
        playback.set_speed(8)
        clock.advance(large * 125 - 1)
        playback.update()
        self.assertEqual(player.current_index, 2)
        self.assertEqual(playback.partial_modeled_us, large - Fraction(1, 125))
        self.assertEqual(player.cumulative_modeled_us, 126022)
        clock.advance(1)
        playback.update()
        self.assertEqual((player.current_index, playback.partial_modeled_us), (3, 0))
        clock.advance(19 * 125)
        playback.update()
        self.assertFalse(playback.running)
        self.assertEqual(player.cumulative_modeled_us, 126041 + large)

    def test_playback_never_plans_reloads_profile_or_changes_execution(self):
        execution = self.player.execution
        before = deepcopy(execution)
        forbidden = (
            "stage3_runner.run_stage3", "stage3_runner.plan_position",
            "stage3_planner.plan_position", "stage3_runner.action_cost",
            "stage3_runner.load_timing_table", "stage3_physical.action_cost",
            "stage3_physical.load_timing_table", "builtins.open", "pathlib.Path.read_bytes",
        )
        with ExitStack() as stack:
            for name in forbidden:
                stack.enter_context(patch(name, side_effect=AssertionError(name)))
            playback = Stage3ModeledPlayback(self.player, clock=self.clock)
            playback.play()
            self.clock.advance(5000)
            playback.pause()
            playback.set_speed(8)
            playback.play()
            self.clock.advance(1000000)
            playback.update()
            playback.cancel_partial()
        self.assertEqual(execution, before)
        self.assertIs(self.player.execution, execution)
        self.assertEqual(execution.result.total_modeled_us, 100)
        self.assertEqual(self.player.cumulative_modeled_us, 100)
        self.assertEqual(self.player.current_index, 4)

    def test_real_game_zero_completes_at_exact_recorded_total(self):
        execution = run_expert_stage3_execution(0)
        before = deepcopy(execution)
        self.assertEqual(len(execution.result.traces), 227)
        self.assertEqual(execution.result.status, GameStatus.WON)
        self.assertEqual(execution.result.total_modeled_us, 39987084)
        player, clock = Stage3TracePlayer(execution), FakeClock()
        playback = Stage3ModeledPlayback(player, clock=clock)
        playback.play()
        clock.advance(39987084 * 1000)
        playback.update()
        self.assertEqual(player.current_index, 227)
        self.assertEqual(player.status, GameStatus.WON)
        self.assertEqual(player.cumulative_modeled_us, 39987084)
        self.assertIs(type(player.cumulative_modeled_us), int)
        self.assertEqual(playback.partial_modeled_us, 0)
        self.assertIsNone(playback.pending_trace)
        self.assertFalse(playback.running)
        self.assertEqual(execution, before)
        clock.advance(1000000000)
        playback.play()
        playback.update()
        self.assertEqual(player.current_index, 227)


if __name__ == "__main__":
    unittest.main()
