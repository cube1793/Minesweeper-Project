"""Exact clock/commit tests; navigation has no execution/evidence IO."""

from fractions import Fraction
import unittest
from unittest.mock import patch

from experiments.random_expert_exhibition_playback import (
    ExhibitionPlayer, ExhibitionPlayback, MODEL_C_MODE, INTERVAL_MODE,
)
from tests.test_random_expert_exhibition_execution import fixture_traces


class ExhibitionPlaybackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v1, cls.k = fixture_traces()

    def setUp(self):
        self.now = 0
        self.player = ExhibitionPlayer(self.k)
        self.clock = ExhibitionPlayback(self.player, clock=lambda: self.now)

    def test_first_last_input_boundaries_and_no_wrap(self):
        self.clock.play()
        self.now = 249_999_999
        self.clock.update()
        self.assertEqual(self.player.current_index, 0)
        self.now += 1
        self.clock.update()
        self.assertEqual(self.player.current_index, 1)
        self.now = len(self.k.actions) * 250_000_000
        self.clock.update()
        self.assertEqual(self.player.current_index, len(self.k.actions))
        self.assertFalse(self.clock.running)
        self.assertEqual(self.player.current_frame.cumulative_modeled_us, self.k.total_modeled_us)
        self.clock.play()
        self.assertEqual(self.player.current_index, len(self.k.actions))

    def test_partial_motion_never_promotes_M_board_route_or_cost(self):
        self.clock.seek(1)
        frame = self.player.current_frame
        route = self.player.completed_route
        self.clock.play()
        self.now = 125_000_000
        self.clock.update()
        self.assertIs(self.player.current_frame, frame)
        self.assertEqual(self.player.completed_route, route)
        self.assertFalse(frame.logical_mines)
        self.assertTrue(self.player.pending_action.preinput_M)
        self.assertNotEqual(self.clock.cursor, frame.cursor)
        self.now = 250_000_000
        self.clock.update()
        self.assertEqual(self.player.current_frame.logical_mines, self.k.actions[1].preinput_M)

    def test_pause_resume_preserves_exact_fraction(self):
        self.clock.play()
        self.now = 100_000_000
        self.clock.pause()
        self.assertEqual(self.clock.progress, Fraction(2, 5))
        self.now += 9_000_000_000
        self.clock.update()
        self.assertEqual(self.player.current_index, 0)
        self.clock.play()
        self.now += 150_000_000
        self.clock.update()
        self.assertEqual(self.player.current_index, 1)

    def test_interval_and_mode_change_preserve_fraction_paused_and_running(self):
        for running in (False, True):
            with self.subTest(running=running):
                self.setUp()
                self.clock.play()
                self.now = 125_000_000
                if not running:
                    self.clock.pause()
                self.clock.set_interval(500)
                self.assertEqual(self.clock.progress, Fraction(1, 2))
                self.clock.set_mode(MODEL_C_MODE)
                self.assertEqual(self.clock.progress, Fraction(1, 2))
                self.assertEqual(self.clock.pending_duration_us, self.k.actions[0].modeled_action_us)
                self.assertEqual(self.clock.running, running)
                self.clock.set_mode(INTERVAL_MODE)
                self.assertEqual(self.clock.progress, Fraction(1, 2))
                self.assertEqual(self.player.current_index, 0)

    def test_model_c_speed_changes_charge_old_rate_and_keep_exact_cost(self):
        self.clock.set_mode(MODEL_C_MODE)
        self.clock.play()
        self.now = 20_000_000
        self.clock.set_speed(2)
        self.assertEqual(self.clock.partial_modeled_us, 20000)
        self.now += (self.k.actions[0].modeled_action_us - 20000) * 500
        self.clock.update()
        self.assertEqual(self.player.current_index, 1)
        self.assertEqual(self.player.current_frame.cumulative_modeled_us, self.k.actions[0].modeled_action_us)

    def test_seek_discards_unsampled_partial_and_rejects_invalid_without_mutation(self):
        self.clock.play()
        self.now = 249_000_000
        self.clock.seek(0)
        self.assertFalse(self.clock.running)
        self.assertEqual(self.clock.progress, 0)
        self.assertEqual(self.player.current_frame.cumulative_modeled_us, 0)
        for index in (-1, True, 1.5, self.player.step_count + 1):
            with self.assertRaises(ValueError):
                self.clock.seek(index)
            self.assertEqual(self.player.current_index, 0)

    def test_independent_players_and_clocks(self):
        other_now = 0
        other = ExhibitionPlayer(self.v1)
        clock = ExhibitionPlayback(other, clock=lambda: other_now)
        clock.play()
        self.clock.play()
        self.now = 500_000_000
        self.clock.update()
        clock.update()
        self.assertEqual((self.player.current_index, other.current_index), (2, 0))
        self.clock.seek(0)
        self.assertTrue(clock.running)

    def test_navigation_never_calls_solvers_engines_or_reads_files(self):
        with patch("builtins.open", side_effect=AssertionError("IO")), \
                patch("core_engine.MinesweeperEngine", side_effect=AssertionError("engine")), \
                patch("experiments.program_k_runner.run_k_p0", side_effect=AssertionError("solver")), \
                patch("experiments.program_k_runner.run_control_capture", side_effect=AssertionError("solver")):
            for index in range(self.player.step_count + 1):
                self.clock.seek(index)
                self.player.current_frame
                self.player.completed_route
            self.clock.seek(0)
            self.clock.play()
            self.now = 10_000_000_000
            self.clock.update()
        self.assertEqual(self.player.current_index, self.player.step_count)

    def test_bad_clock_stops_without_early_commit(self):
        self.clock.play()
        self.now = 20
        self.clock.update()
        self.now = 19
        with self.assertRaises(ValueError):
            self.clock.update()
        self.assertFalse(self.clock.running)
        self.assertEqual(self.player.current_index, 0)

    def test_invalid_settings_rejected_without_change(self):
        for interval in (True, False, 0, -1, 19.999, 10000.001, "250", None,
                         float("nan"), float("inf"), -float("inf")):
            with self.assertRaises(ValueError):
                self.clock.set_interval(interval)
        for cps in (True, False, 0, -1, .0999, 50.001, "3", None,
                    float("nan"), float("inf"), -float("inf")):
            with self.assertRaises(ValueError):
                self.clock.set_cps(cps)
        for speed in (True, 0, 3, 16):
            with self.assertRaises(ValueError):
                self.clock.set_speed(speed)
        with self.assertRaises(ValueError):
            self.clock.set_mode("human_time")
        self.assertEqual((self.clock.interval_ms, self.clock.mode), (250, INTERVAL_MODE))

    def test_presets_custom_ms_and_range_endpoints_have_one_exact_duration(self):
        for value in (250, 200, 500, 249, 1000, 250.0, 123.456, 20, 10000):
            self.clock.set_interval(value)
            expected = Fraction(str(value))
            self.assertEqual(self.clock.interval_ms, expected)
            self.assertEqual(self.clock.interval_us, expected * 1000)
            self.assertEqual(self.clock.cps, 1000 / expected)
        for cps, milliseconds in ((.1, 10000), (50, 20), (5, 200), (2, 500), (4, 250)):
            self.clock.set_cps(cps)
            self.assertEqual(self.clock.interval_ms, milliseconds)

    def test_three_cps_exact_reciprocal_and_first_input_nanosecond_boundary(self):
        self.clock.set_cps(3)
        self.assertEqual(self.clock.interval_us, Fraction(1_000_000, 3))
        self.assertEqual(self.clock.interval_ms, Fraction(1000, 3))
        self.assertEqual(self.clock.cps, 3)
        first = self.player.current_frame
        self.clock.play()
        self.now = 333_333_333
        self.clock.update()
        self.assertIs(self.player.current_frame, first)
        self.assertEqual(self.player.completed_route, ())
        self.now += 1
        self.clock.update()
        self.assertEqual(self.player.current_index, 1)
        self.assertEqual(self.player.current_frame.cumulative_modeled_us, self.k.actions[0].modeled_action_us)

    def test_custom_changes_charge_old_rate_preserve_partial_and_commit_only_at_boundary(self):
        self.clock.seek(1)
        frame = self.player.current_frame
        route = self.player.completed_route
        self.clock.play()
        self.now = 100_000_000  # 2/5 of the old 250 ms interval, not yet sampled
        self.clock.set_cps(3)
        self.assertEqual(self.clock.progress, Fraction(2, 5))
        self.assertTrue(self.clock.running)
        self.assertIs(self.player.current_frame, frame)
        self.assertEqual(self.player.completed_route, route)
        self.now += 199_999_999
        self.clock.update()
        self.assertIs(self.player.current_frame, frame)
        self.assertFalse(frame.logical_mines)
        self.now += 1
        self.clock.update()
        self.assertEqual(self.player.current_index, 2)
        self.assertEqual(self.player.current_frame.logical_mines, self.k.actions[1].preinput_M)
        self.assertEqual(self.player.current_frame.cumulative_modeled_us,
                         sum(a.modeled_action_us for a in self.k.actions[:2]))

    def test_paused_custom_and_model_switch_preserve_exact_fraction_and_model_cost(self):
        self.clock.play()
        self.now = 125_000_000
        self.clock.pause()
        original_costs = tuple(a.modeled_action_us for a in self.k.actions)
        for setting in (3, 7, .1, 50):
            self.clock.set_cps(setting)
            self.assertEqual(self.clock.progress, Fraction(1, 2))
            interval = self.clock.interval_us
            self.clock.set_mode(MODEL_C_MODE)
            self.clock.set_speed(8)
            self.assertEqual(self.clock.pending_duration_us, original_costs[0])
            self.assertEqual(self.clock.progress, Fraction(1, 2))
            self.clock.set_mode(INTERVAL_MODE)
            self.assertEqual(self.clock.interval_us, interval)
            self.assertEqual(self.clock.progress, Fraction(1, 2))
            self.assertFalse(self.clock.running)
            self.assertEqual(self.player.current_index, 0)
        self.assertEqual(tuple(a.modeled_action_us for a in self.k.actions), original_costs)


if __name__ == "__main__":
    unittest.main()
