"""Deterministic presentation clocks over handwritten native stream facts.

No solver, board generation, Model C authentication or real sleep is needed.
Existing SameBoardPlayback regressions separately protect committed board replay.
"""

from dataclasses import FrozenInstanceError, fields, replace
from fractions import Fraction
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from core_engine import Action, GameStatus
from replay_model import ReplayEvent
from simple_algorithm import SimpleMove
from stage3_runner import Stage3ActionTrace, Stage3RunResult
from same_board_timed_playback import (
    PlaybackMode, RunTiming, SameBoardTimedPlayback, TimingAuthority,
    project_human_timing, project_same_board_timings,
    project_stage2_timing, project_stage3_timing,
)


class Clock:
    def __init__(self):
        self.ns = 0
        self.reads = 0

    def __call__(self):
        self.reads += 1
        return self.ns


def human(times=(0.5, 1.0, 2.0), targets=((2, 1), (0, 1), (0, 1))):
    return tuple(ReplayEvent(t, x, y, "OPEN") for t, (x, y) in zip(times, targets))


def traces(costs=(100_000, 200_000, 300_000), targets=((0, 0), (2, 1), (2, 1))):
    result, cursor = [], (0, 0)
    for i, (cost, target) in enumerate(zip(costs, targets)):
        result.append(Stage3ActionTrace(
            SimpleMove(Action.OPEN, *target), None, None, cursor, cost,
            GameStatus.LOST if i == len(costs) - 1 else GameStatus.PLAYING, 0, 0,
        ))
        cursor = target
    return tuple(result)


def solver_timing():
    return project_stage3_timing(traces(), initial_cursor=(0, 0), final_total_us=600_000)


class RecordingTable:
    """Asymmetric literal lookup oracle; disabled after projection."""
    def __init__(self):
        self.cells = {(0, 0): 7, (2, 1): 11, (1, 0): 13}
        self.lookups = []
        self.enabled = True

    def __getitem__(self, dx):
        table = self

        class Row:
            def __getitem__(self, dy):
                if not table.enabled:
                    raise AssertionError("Timing table accessed after projection")
                table.lookups.append((dx, dy))
                return table.cells[dx, dy]

        return Row()


class ProjectionTests(unittest.TestCase):
    def test_human_preserves_order_preludes_repeated_targets_and_original_values(self):
        events = (
            ReplayEvent(0.5, 2, 1, "CHORD"),
            ReplayEvent(0.75, 1, 0, "FLAG"),
            ReplayEvent(0.75, 1, 0, "FLAG"),
            ReplayEvent(2, 0, 0, "OPEN"),
        )
        before = tuple(events)
        projection = project_human_timing(iter(events))
        self.assertEqual(projection.targets, ((2, 1), (1, 0), (1, 0), (0, 0)))
        self.assertEqual(projection.completion_times,
                         (Fraction(1, 2), Fraction(3, 4), Fraction(3, 4), Fraction(2)))
        self.assertEqual(projection.action_count, 4)
        self.assertIs(projection.authority, TimingAuthority.REPLAY_TIME)
        self.assertEqual(projection.time_unit, "seconds")
        self.assertEqual(events, before)

    def test_human_float_is_exact_stored_binary_value_not_decimal_or_microseconds(self):
        projection = project_human_timing(human((0.1, 0.2, 0.3)))
        self.assertEqual(projection.completion_times, (
            Fraction(3602879701896397, 36028797018963968),
            Fraction(3602879701896397, 18014398509481984),
            Fraction(5404319552844595, 18014398509481984),
        ))
        self.assertNotEqual(projection.completion_times[0], Fraction(1, 10))
        self.assertTrue(all(type(value) is Fraction for value in projection.completion_times))

    def test_human_zero_and_equal_timestamps_are_retained(self):
        projection = project_human_timing(human((0, 0, 0.5)))
        self.assertEqual(projection.completion_times, (Fraction(0), Fraction(0), Fraction(1, 2)))
        self.assertEqual(projection.targets, ((2, 1), (0, 1), (0, 1)))

    def test_human_initial_cursor_is_first_target_not_a_declared_solver_origin(self):
        projection = project_human_timing(human())
        self.assertEqual(projection.initial_cursor, (2, 1))
        self.assertIn("synthetic", projection.initial_cursor_policy)
        self.assertIn("no recorded prior origin", projection.initial_cursor_policy)
        state = SameBoardTimedPlayback(projection).state
        self.assertEqual((state.segment_start, state.segment_end), ((2, 1), (2, 1)))
        self.assertTrue(state.stationary)

    def test_human_invalid_times_fail_instead_of_being_rounded_or_sorted(self):
        for invalid in (True, -1, float("nan"), float("inf"), "0.1", Fraction(1, 2)):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                project_human_timing((SimpleNamespace(elapsed_time=invalid, x=0, y=0),))
        with self.assertRaisesRegex(ValueError, "nondecreasing"):
            project_human_timing(human((1, 0.5, 2)))

    def test_stage2_uses_exact_table_axes_and_authoritative_cursor_progression(self):
        table = RecordingTable()
        projection = project_stage2_timing(
            ((3, 2), (5, 3), (4, 3)), table=table,
            initial_cursor=(3, 2), final_total_us=31,
        )
        self.assertEqual(table.lookups, [(0, 0), (2, 1), (1, 0)])
        self.assertEqual(projection.completion_times, (7, 18, 31))
        self.assertTrue(all(type(value) is int for value in projection.completion_times))
        self.assertEqual(projection.initial_cursor, (3, 2))
        self.assertEqual(projection.initial_cursor_policy, "retained Model C initial cursor")
        self.assertEqual(projection.time_unit, "microseconds")
        self.assertEqual(projection.total_time, 31)

    def test_stage2_final_total_mismatch_fails(self):
        with self.assertRaisesRegex(ValueError, "Stage-2 projected total"):
            project_stage2_timing(((0, 0),), table=((7,),), initial_cursor=(0, 0), final_total_us=8)

    def test_stage2_has_no_table_access_after_projection_in_either_mode(self):
        table = RecordingTable()
        timing = project_stage2_timing(
            ((3, 2), (5, 3), (4, 3)), table=table,
            initial_cursor=(3, 2), final_total_us=31,
        )
        table.enabled = False
        clock = Clock()
        player = SameBoardTimedPlayback(timing, clock=clock)
        for mode in (PlaybackMode.INDEX, PlaybackMode.MODEL_C_TIME):
            player.set_mode(mode)
            player.align(0)
            player.play()
            clock.ns += 2_000_000_000
            self.assertTrue(player.update().terminal)
        self.assertEqual(table.lookups, [(0, 0), (2, 1), (1, 0)])
        self.assertNotIn(table, vars(player).values())

    def test_stage2_invalid_costs_totals_and_out_of_table_displacements_fail(self):
        for cost in (True, -1, 1.0, "7"):
            with self.subTest(cost=cost), self.assertRaises(ValueError):
                project_stage2_timing(((0, 0),), table=((cost,),), initial_cursor=(0, 0), final_total_us=7)
        for total in (True, -1, 7.0):
            with self.subTest(total=total), self.assertRaises(ValueError):
                project_stage2_timing(((0, 0),), table=((7,),), initial_cursor=(0, 0), final_total_us=total)
        with self.assertRaisesRegex(ValueError, "outside"):
            project_stage2_timing(((2, 1),), table=((7,),), initial_cursor=(0, 0), final_total_us=7)

    def test_stage3_costs_come_from_traces_even_for_identical_targets(self):
        recorded = traces((7, 11, 2**60 + 1), ((0, 0), (0, 0), (0, 0)))
        projection = project_stage3_timing(recorded, initial_cursor=(0, 0), final_total_us=2**60 + 19)
        self.assertEqual(projection.completion_times, (7, 18, 2**60 + 19))
        self.assertTrue(all(type(value) is int for value in projection.completion_times))
        self.assertEqual(tuple(t.modeled_action_us for t in recorded), (7, 11, 2**60 + 1))

    def test_stage3_zero_duration_and_retained_initial_cursor(self):
        projection = project_stage3_timing(traces((0, 7, 0)), initial_cursor=(4, 3), final_total_us=7)
        self.assertEqual(projection.completion_times, (0, 7, 7))
        self.assertEqual(projection.initial_cursor, (4, 3))

    def test_stage3_invalid_cost_or_mismatched_total_fails(self):
        for cost in (True, -1, 1.25):
            with self.subTest(cost=cost), self.assertRaises(ValueError):
                project_stage3_timing(traces((cost,)), initial_cursor=(0, 0), final_total_us=0)
        with self.assertRaisesRegex(ValueError, "Stage-3 recorded sum"):
            project_stage3_timing(traces(), initial_cursor=(0, 0), final_total_us=600001)

    def test_empty_completed_streams_are_rejected_for_all_three_roles(self):
        constructors = (
            lambda: project_human_timing(()),
            lambda: project_stage2_timing((), table=(), initial_cursor=(0, 0), final_total_us=0),
            lambda: project_stage3_timing((), initial_cursor=(0, 0), final_total_us=0),
        )
        for construct in constructors:
            with self.subTest(construct=construct), self.assertRaises(ValueError):
                construct()

    def test_projection_is_deeply_immutable_and_retains_no_events_or_table(self):
        targets, boundaries, initial = [[2, 1], [0, 1]], [Fraction(1), Fraction(2)], [2, 1]
        projection = RunTiming(TimingAuthority.REPLAY_TIME, targets, boundaries, initial)
        targets[0][0] = 99
        boundaries.clear()
        initial[0] = 99
        self.assertEqual(projection.targets, ((2, 1), (0, 1)))
        self.assertEqual(projection.completion_times, (Fraction(1), Fraction(2)))
        self.assertEqual(projection.initial_cursor, (2, 1))
        with self.assertRaises(FrozenInstanceError):
            projection.initial_cursor = (0, 0)
        self.assertEqual({field.name for field in fields(projection)},
                         {"authority", "targets", "completion_times", "initial_cursor"})

    def test_projection_rejects_wrong_authority_units_coordinates_and_alignment(self):
        good = solver_timing()
        changes = (
            {"authority": "Model C Time"}, {"targets": ((True, 0),) * 3},
            {"initial_cursor": (-1, 0)}, {"completion_times": (1, 2)},
            {"completion_times": (1, -1, 3)}, {"completion_times": (1, 0, 3)},
            {"completion_times": (1, Fraction(2), 3)},
        )
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(good, **change)
        with self.assertRaises(ValueError):
            replace(project_human_timing(human()), initial_cursor=(0, 0))
        with self.assertRaises(ValueError):
            replace(project_human_timing(human()), completion_times=(1, 2, 3))

    def execution_projection_fixture(self):
        # Structural adapter fixture: native events/results with no admission,
        # solver, Engine or authentication execution. The caller owns admission.
        class HumanReplay:
            events = human()

            @property
            def mouse_trace(self):
                raise AssertionError("Do not borrow Mouse Trace as cursor/time authority")

        result = Stage3RunResult(GameStatus.LOST, traces((7, 11, 13)))
        return SimpleNamespace(
            context=SimpleNamespace(human_replay=HumanReplay()),
            stage2_result=SimpleNamespace(moves=tuple(SimpleMove(Action.OPEN, *xy)
                for xy in ((0, 0), (2, 1), (1, 1)))),
            stage2_metrics=SimpleNamespace(model_c_total_us=31),
            stage3_result=result, stage3_metrics=SimpleNamespace(model_c_total_us=31),
            model_c_evaluation=SimpleNamespace(table=RecordingTable(), initial_cursor=(0, 0)),
        )

    def test_composition_uses_native_roles_and_does_not_retain_execution(self):
        execution = self.execution_projection_fixture()
        timings = project_same_board_timings(execution)
        self.assertEqual(timings.human.initial_cursor, (2, 1))
        self.assertEqual(timings.stage2.completion_times, (7, 18, 31))
        self.assertEqual(timings.stage3.completion_times, (7, 18, 31))
        self.assertEqual(timings.stage2.initial_cursor, execution.model_c_evaluation.initial_cursor)
        self.assertEqual(timings.stage3.initial_cursor, execution.model_c_evaluation.initial_cursor)
        execution.stage2_result.moves = ()
        execution.model_c_evaluation.table.enabled = False
        self.assertEqual(timings.stage2.targets, ((0, 0), (2, 1), (1, 1)))
        self.assertEqual(set(vars(timings)), {"human", "stage2", "stage3"})
        with self.assertRaises(FrozenInstanceError):
            timings.human = timings.stage2

    def test_composition_reconciles_stage3_metrics_and_native_result_total(self):
        execution = self.execution_projection_fixture()
        execution.stage3_metrics.model_c_total_us = 32
        with self.assertRaisesRegex(ValueError, "Stage-3 recorded sum"):
            project_same_board_timings(execution)
        execution.stage3_metrics.model_c_total_us = 31
        execution.stage3_result = SimpleNamespace(traces=traces((7, 11, 13)), total_modeled_us=32)
        with self.assertRaisesRegex(ValueError, "native result total"):
            project_same_board_timings(execution)


class TimingControllerTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.player = SameBoardTimedPlayback(solver_timing(), clock=self.clock)

    def time_mode(self, timing=None):
        player = self.player if timing is None else SameBoardTimedPlayback(timing, clock=self.clock)
        player.set_mode(PlaybackMode(player.timing.authority.value))
        return player

    def test_default_state_has_exact_pending_zero_index_and_solver_origin(self):
        state = self.player.state
        self.assertEqual(self.player.interval_ms, 200)
        self.assertEqual(self.player.speed, Fraction(1))
        self.assertEqual((state.completed_index, state.pending_action_index), (0, 0))
        self.assertEqual((state.segment_start, state.segment_end), ((0, 0), (0, 0)))
        self.assertEqual((state.progress, state.playhead), (0, 0))
        self.assertEqual(state.playhead_unit, "actions")
        self.assertIs(state.mode, PlaybackMode.INDEX)
        self.assertFalse(state.running)
        self.assertFalse(state.terminal)

    def test_index_raw_quarters_are_not_eased_and_commit_only_at_exact_boundary(self):
        p = self.player
        p.align(1)
        p.set_interval(1000)
        p.play()
        for elapsed_ns, u in ((0, 0), (250000000, Fraction(1, 4)),
                              (500000000, Fraction(1, 2)), (750000000, Fraction(3, 4)),
                              (999999999, Fraction(999999999, 1000000000))):
            self.clock.ns = elapsed_ns
            state = p.update()
            self.assertEqual(state.completed_index, 1)
            self.assertEqual(state.pending_action_index, 1)
            self.assertEqual(state.progress, u)
            self.assertEqual((state.segment_start, state.segment_end), ((0, 0), (2, 1)))
        self.clock.ns = 1000000000
        self.assertEqual(p.update().completed_index, 2)
        self.assertEqual(p.state.progress, 0)

    def test_index_bounds_default_and_exact_lower_upper_durations(self):
        for interval in (20, 200, 5000):
            with self.subTest(interval=interval):
                self.player.align(0)
                self.player.set_interval(interval)
                self.player.play()
                self.clock.ns += interval * 1000000 - 1
                self.assertEqual(self.player.update().completed_index, 0)
                self.clock.ns += 1
                self.assertEqual(self.player.update().completed_index, 1)

    def test_index_late_tick_returns_final_due_prefix_without_duplicate_advancement(self):
        p = self.player
        p.play()
        self.clock.ns = 450000000
        state = p.update()
        self.assertEqual((state.completed_index, state.pending_action_index, state.progress),
                         (2, 2, Fraction(1, 4)))
        self.assertEqual(state.playhead, Fraction(9, 4))
        self.assertEqual(p.update(), state)
        self.assertEqual(p.timing.targets[:state.completed_index], ((0, 0), (2, 1)))

    def test_time_modes_follow_distinct_native_units(self):
        human_player = self.time_mode(project_human_timing(human()))
        model_player = self.time_mode()
        human_player.play()
        model_player.play()
        self.clock.ns = 150000000
        h, m = human_player.update(), model_player.update()
        self.assertEqual((h.playhead, h.playhead_unit, h.completed_index), (Fraction(3, 20), "seconds", 0))
        self.assertEqual((m.playhead, m.playhead_unit, m.completed_index), (150000, "microseconds", 1))
        self.assertEqual(m.progress, Fraction(1, 4))

    def test_human_initial_delay_is_stationary_until_original_boundary(self):
        p = self.time_mode(project_human_timing(human()))
        p.play()
        self.clock.ns = 250000000
        state = p.update()
        self.assertEqual((state.completed_index, state.progress), (0, Fraction(1, 2)))
        self.assertEqual((state.segment_start, state.segment_end), ((2, 1), (2, 1)))
        self.assertTrue(state.stationary)
        self.clock.ns = 500000000
        state = p.update()
        self.assertEqual(state.completed_index, 1)
        self.assertEqual((state.segment_start, state.segment_end), ((2, 1), (0, 1)))

    def test_human_index_first_action_is_stationary_regardless_of_replay_delay(self):
        p = SameBoardTimedPlayback(project_human_timing(human()), clock=self.clock)
        p.play()
        self.clock.ns = 100000000
        state = p.update()
        self.assertEqual((state.completed_index, state.progress), (0, Fraction(1, 2)))
        self.assertTrue(state.stationary)
        self.clock.ns = 200000000
        self.assertEqual(p.update().completed_index, 1)

    def test_human_zero_first_and_equal_timestamps_catch_up_in_recorded_order(self):
        p = self.time_mode(project_human_timing(human((0, 0, 0.5))))
        self.assertEqual(p.state.completed_index, 0)
        state = p.play()
        self.assertEqual(state.completed_index, 2)
        self.assertEqual(p.timing.targets[:state.completed_index], ((2, 1), (0, 1)))
        self.assertEqual(state.progress, 0)
        self.clock.ns = 500000000
        self.assertTrue(p.update().terminal)

    def test_equal_nonzero_time_actions_are_included_at_exact_boundary(self):
        p = self.time_mode(project_human_timing(human((0.5, 0.5, 2))))
        p.play()
        self.clock.ns = 499999999
        self.assertEqual(p.update().completed_index, 0)
        self.clock.ns += 1
        self.assertEqual(p.update().completed_index, 2)
        self.assertEqual(p.state.progress, 0)

    def test_exact_float_boundary_does_not_commit_at_rounded_decimal_time(self):
        p = self.time_mode(project_human_timing(human((0.1, 0.2, 0.3))))
        p.play()
        self.clock.ns = 100000000
        self.assertEqual(p.update().completed_index, 0)  # Stored 0.1 is greater than 1/10.
        self.clock.ns += 1
        self.assertEqual(p.update().completed_index, 1)
        self.clock.ns = 300000000
        self.assertTrue(p.update().terminal)
        self.assertEqual(p.state.playhead, Fraction(5404319552844595, 18014398509481984))

    def test_stage2_time_consumes_projected_prefixes_exactly(self):
        timing = project_stage2_timing(((0, 0), (2, 1), (1, 1)), table=RecordingTable(),
                                      initial_cursor=(0, 0), final_total_us=31)
        p = self.time_mode(timing)
        p.play()
        for ns, k in ((6999, 0), (7000, 1), (17999, 1), (18000, 2), (31000, 3)):
            self.clock.ns = ns
            self.assertEqual(p.update().completed_index, k)
        self.assertEqual(p.state.playhead, 31)
        self.assertFalse(p.state.running)

    def test_stage3_time_exact_recorded_boundaries_and_final_clamp(self):
        p = self.time_mode()
        p.play()
        for ns, k in ((99999999, 0), (100000000, 1), (299999999, 1),
                      (300000000, 2), (599999999, 2), (600000000, 3)):
            self.clock.ns = ns
            self.assertEqual(p.update().completed_index, k)
        self.assertEqual(p.state.playhead, 600000)
        self.assertFalse(p.state.running)

    def test_zero_duration_solver_actions_and_all_zero_stream_stop_without_division(self):
        for costs, k in (((0, 7, 0), 1), ((0, 0, 0), 3)):
            p = self.time_mode(project_stage3_timing(traces(costs), initial_cursor=(0, 0), final_total_us=sum(costs)))
            state = p.play()
            self.assertEqual(state.completed_index, k)
            self.assertEqual(state.progress, 0)
            if k == 1:
                self.clock.ns += 7000
                self.assertEqual(p.update().completed_index, 3)
            self.assertFalse(p.state.running)

    def test_late_time_tick_crosses_multiple_actions_and_preserves_pending_fraction(self):
        p = self.time_mode()
        p.play()
        self.clock.ns = 375000000
        state = p.update()
        self.assertEqual((state.completed_index, state.progress), (2, Fraction(1, 4)))
        self.assertEqual(state.playhead, 375000)
        self.assertTrue(state.stationary)
        self.assertEqual(p.update(), state)

    def test_quarter_one_and_eight_speed_scaling_for_both_time_authorities(self):
        for timing in (project_human_timing(human()), solver_timing()):
            for speed, seconds in ((0.25, Fraction(1, 100)), (1, Fraction(1, 25)), (8, Fraction(8, 25))):
                with self.subTest(authority=timing.authority, speed=speed):
                    p = self.time_mode(timing)
                    p.set_speed(speed)
                    p.play()
                    self.clock.ns += 40000000
                    state = p.update()
                    expected = seconds if timing.authority is TimingAuthority.REPLAY_TIME else seconds * 1000000
                    self.assertEqual(state.playhead, expected)

    def test_every_exact_quarter_speed_is_supported_without_float_authority(self):
        for quarter in range(1, 33):
            self.player.set_speed(quarter / 4)
            self.assertEqual(self.player.speed, Fraction(quarter, 4))
            self.assertIs(type(self.player.speed), Fraction)

    def test_fractional_microseconds_do_not_accumulate_tick_rounding(self):
        p = self.time_mode()
        p.set_speed(0.25)
        p.play()
        for ns in range(1, 4001):
            self.clock.ns = ns
            p.update()
            if ns == 1:
                self.assertEqual(p.state.playhead, Fraction(1, 4000))
        self.assertEqual(p.state.playhead, 1)
        self.assertEqual(p.timing.completion_times, (100000, 300000, 600000))

    def test_active_speed_change_accounts_old_rate_then_continues_without_jump(self):
        p = self.time_mode()
        p.play()
        self.clock.ns = 150000000
        state = p.set_speed(2)
        self.assertEqual((state.completed_index, state.progress, state.playhead), (1, Fraction(1, 4), 150000))
        self.assertTrue(state.running)
        self.assertEqual(p.update(), state)
        self.clock.ns += 25000000
        self.assertEqual(p.update().playhead, 200000)
        p.set_speed(Fraction(1, 4))
        self.assertEqual(p.state.playhead, 200000)
        self.clock.ns += 40000000
        self.assertEqual(p.update().playhead, 210000)

    def test_active_interval_change_preserves_fraction_uses_new_remaining_duration(self):
        p = self.player
        p.set_interval(1000)
        p.align(1)
        p.play()
        self.clock.ns = 250000000
        self.assertEqual(p.set_interval(2000).progress, Fraction(1, 4))
        self.assertTrue(p.state.running)
        self.clock.ns += 1000000000
        self.assertEqual(p.update().progress, Fraction(3, 4))
        self.assertEqual(p.state.completed_index, 1)
        self.clock.ns += 500000000
        self.assertEqual(p.update().completed_index, 2)

    def test_inactive_rate_control_does_not_read_clock_or_change_playhead(self):
        for mode in (PlaybackMode.INDEX, PlaybackMode.MODEL_C_TIME):
            self.player.set_mode(mode)
            self.player.align(0)
            self.player.play()
            before, reads = self.player.state, self.clock.reads
            self.clock.ns += 1000
            if mode is PlaybackMode.INDEX:
                self.player.set_speed(8)
            else:
                self.player.set_interval(20)
            self.assertEqual(self.clock.reads, reads)
            self.assertEqual(self.player.state, before)

    def test_pause_samples_unsampled_time_resume_excludes_paused_wall_time(self):
        for mode, duration_ns in ((PlaybackMode.INDEX, 200000000), (PlaybackMode.MODEL_C_TIME, 100000000)):
            p = self.player
            p.set_mode(mode)
            p.align(0)
            p.play()
            self.clock.ns += duration_ns // 4
            paused = p.pause()
            self.assertEqual(paused.progress, Fraction(1, 4))
            self.assertFalse(paused.running)
            self.clock.ns += 10000000000
            self.assertEqual(p.update(), paused)
            resumed = p.play()
            self.assertEqual(resumed, replace(paused, running=True))
            self.clock.ns += duration_ns // 2
            self.assertEqual(p.update().progress, Fraction(3, 4))

    def test_human_pause_resume_preserves_exact_rational_seconds(self):
        p = self.time_mode(project_human_timing(human()))
        p.play()
        self.clock.ns = 123456789
        paused = p.pause()
        self.assertEqual(paused.playhead, Fraction(123456789, 1000000000))
        self.clock.ns += 999999999
        p.play()
        self.assertEqual(p.state.playhead, paused.playhead)
        self.clock.ns += 1
        self.assertEqual(p.update().playhead, Fraction(123456790, 1000000000))

    def test_manual_alignment_discards_partial_and_unsampled_time_at_requested_index(self):
        p = self.time_mode()
        p.play()
        self.clock.ns = 150000000
        self.assertEqual(p.update().progress, Fraction(1, 4))
        self.clock.ns = 550000000
        state = p.align(1)
        self.assertEqual((state.completed_index, state.playhead, state.progress), (1, 100000, 0))
        self.assertFalse(state.running)
        self.assertEqual((state.segment_start, state.segment_end), ((0, 0), (2, 1)))
        p.align(0)
        self.assertEqual(p.state.playhead, 0)
        p.align(3)
        self.assertTrue(p.state.terminal)
        self.assertEqual(p.state.playhead, 600000)

    def test_equal_time_manual_alignment_keeps_requested_prefix_until_play(self):
        p = self.time_mode(project_human_timing(human((0.5, 0.5, 2))))
        state = p.align(1)
        self.assertEqual((state.completed_index, state.progress, state.playhead), (1, 0, Fraction(1, 2)))
        self.assertEqual(p.state, state)
        self.assertEqual(p.play().completed_index, 2)

    def test_stop_and_mode_switch_cancel_partial_keep_last_sampled_completed_prefix(self):
        p = self.player
        p.play()
        self.clock.ns = 250000000
        self.assertEqual(p.update().completed_index, 1)
        self.clock.ns += 1000000000  # Manual mode/stop must not commit unsampled actions.
        state = p.set_mode(PlaybackMode.MODEL_C_TIME)
        self.assertEqual((state.completed_index, state.playhead, state.progress), (1, 100000, 0))
        self.assertFalse(state.running)
        p.play()
        self.clock.ns += 50000000
        self.assertEqual(p.update().progress, Fraction(1, 4))
        self.assertEqual(p.stop().playhead, 100000)
        p.set_mode(PlaybackMode.INDEX)
        self.assertEqual(p.state.playhead, 1)

    def test_same_mode_selection_is_inert_and_timing_authorities_cannot_be_swapped(self):
        p = self.player
        p.play()
        before, reads = p.state, self.clock.reads
        self.assertEqual(p.set_mode(PlaybackMode.INDEX), before)
        self.assertEqual(self.clock.reads, reads)
        for player, invalid in ((p, PlaybackMode.REPLAY_TIME),
                                (self.time_mode(project_human_timing(human())), PlaybackMode.MODEL_C_TIME)):
            before = player.state
            with self.assertRaises(ValueError):
                player.set_mode(invalid)
            self.assertEqual(player.state, before)

    def test_repeated_target_segment_stays_stationary_with_positive_duration(self):
        p = self.time_mode()
        p.align(2)
        p.play()
        self.clock.ns = 150000000
        state = p.update()
        self.assertTrue(state.stationary)
        self.assertEqual(state.progress, Fraction(1, 2))
        self.assertEqual((state.segment_start, state.segment_end), ((2, 1), (2, 1)))

    def test_terminal_clamps_stops_keeps_final_cursor_and_never_wraps(self):
        for mode, maximum in ((PlaybackMode.INDEX, 3), (PlaybackMode.MODEL_C_TIME, 600000)):
            p = self.player
            p.set_mode(mode)
            p.align(0)
            p.play()
            self.clock.ns += 100000000000
            state = p.update()
            self.assertEqual(state.completed_index, 3)
            self.assertIsNone(state.pending_action_index)
            self.assertEqual((state.segment_start, state.segment_end), ((2, 1), (2, 1)))
            self.assertEqual(state.playhead, maximum)
            self.assertEqual(state.progress, 0)
            self.assertFalse(state.running)
            reads = self.clock.reads
            self.assertEqual(p.play(), state)
            self.assertEqual(p.update(), state)
            self.assertEqual(self.clock.reads, reads)

    def test_three_run_states_are_independent_even_with_one_wall_clock(self):
        h = SameBoardTimedPlayback(project_human_timing(human()), clock=self.clock)
        s2 = SameBoardTimedPlayback(project_stage2_timing(
            ((0, 0), (2, 1), (1, 1)), table=RecordingTable(), initial_cursor=(0, 0), final_total_us=31),
            clock=self.clock)
        s3 = self.player
        originals = (h.state, s2.state, s3.state)
        h.play()
        self.clock.ns = 250000000
        h.pause()
        self.assertEqual((s2.state, s3.state), originals[1:])
        h_saved = h.state
        s2.set_mode(PlaybackMode.MODEL_C_TIME)
        s2.play()
        self.clock.ns += 8000
        s2.pause()
        self.assertEqual(s2.state.completed_index, 1)
        self.assertEqual(h.state, h_saved)
        self.assertEqual(s3.state, originals[2])
        s2_saved = s2.state
        s3.align(2)
        s3.set_interval(20)
        s3.play()
        self.clock.ns += 20000000
        self.assertTrue(s3.update().terminal)
        self.assertEqual((h.state, s2.state), (h_saved, s2_saved))
        h.play()
        self.assertEqual(h.state.progress, Fraction(1, 4))

    def test_state_is_immutable_clock_free_and_contains_no_paint_or_board_object(self):
        p = self.player
        state = p.state
        with self.assertRaises(FrozenInstanceError):
            state.completed_index = 2
        self.assertEqual(self.clock.reads, 0)
        p.play()
        before, reads = p.state, self.clock.reads
        self.clock.ns += 999999999
        self.assertEqual(p.state, before)
        self.assertEqual(self.clock.reads, reads)
        self.assertEqual(state.progress, 0)
        self.assertTrue(all(isinstance(value, (int, bool, tuple, Fraction, str, PlaybackMode))
                            or value is None for value in vars(state).values()))

    def test_invalid_config_and_alignment_do_not_advance_or_mutate_state(self):
        p = self.player
        p.play()
        self.clock.ns = 500000000
        before, reads = p.state, self.clock.reads
        cases = (
            (p.set_interval, (19, 5001, True, 200.0, "200")),
            (p.set_speed, (0, 0.1, 8.25, True, float("nan"), float("inf"), "1")),
            (p.align, (-1, 4, True, 1.0)),
            (p.set_mode, ("Index", None)),
        )
        for method, values in cases:
            for value in values:
                with self.subTest(method=method.__name__, value=value), self.assertRaises(ValueError):
                    method(value)
                self.assertEqual(p.state, before)
                self.assertEqual(self.clock.reads, reads)

    def test_bad_clock_stops_without_losing_last_valid_presentation_state(self):
        for invalid in (True, 1.25, -1, None, RuntimeError("clock failed")):
            with self.subTest(invalid=invalid):
                clock = Mock(side_effect=[0, 150000000, invalid])
                p = SameBoardTimedPlayback(solver_timing(), clock=clock)
                p.set_mode(PlaybackMode.MODEL_C_TIME)
                p.play()
                prior = p.update()
                with self.assertRaises((ValueError, RuntimeError)):
                    p.pause()
                self.assertEqual(p.state, replace(prior, running=False))
        p = self.time_mode()
        p.play()
        self.clock.ns = 150000000
        prior = p.update()
        self.clock.ns -= 1
        with self.assertRaisesRegex(ValueError, "backwards"):
            p.update()
        self.assertEqual(p.state, replace(prior, running=False))

    def test_repeated_play_does_not_reschedule_or_lose_elapsed_time(self):
        p = self.player
        p.play()
        reads = self.clock.reads
        self.clock.ns = 150000000
        p.play()
        self.assertEqual(self.clock.reads, reads)
        self.clock.ns = 200000000
        self.assertEqual(p.update().completed_index, 1)


class DependencyBoundaryTests(unittest.TestCase):
    def test_clean_process_import_and_operations_need_no_qt_engine_or_domain_modules(self):
        code = '''
import importlib.abc, sys
class RejectDomain(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        root = fullname.split('.')[0]
        if root.startswith(('PyQt', 'PySide', 'simple_', 'stage3_', 'benchmark_', 'telemetry_', 'zini_')) or root in {
                'core_engine', 'replay_model', 'replay_player', 'same_board_playback',
                'same_board_runner', 'same_board_comparison', 'sqlite3'}:
            raise AssertionError('Forbidden runtime import: ' + fullname)
sys.meta_path.insert(0, RejectDomain())
from same_board_timed_playback import *
from types import SimpleNamespace as S
clock = [0]
human = project_human_timing((S(elapsed_time=0, x=1, y=0), S(elapsed_time=0.5, x=0, y=0)))
stage2 = project_stage2_timing(((0, 0), (1, 0)), table=((7,), (11,)), initial_cursor=(0, 0), final_total_us=18)
stage3 = project_stage3_timing((S(move=S(x=0, y=0), modeled_action_us=9),), initial_cursor=(0, 0), final_total_us=9)
for timing in (human, stage2, stage3):
    p = SameBoardTimedPlayback(timing, clock=lambda: clock[0])
    p.set_mode(PlaybackMode(timing.authority.value))
    p.play()
    clock[0] += 1000000000
    assert p.update().terminal
assert not any(name.startswith(('PyQt', 'PySide')) for name in sys.modules)
'''
        result = subprocess.run(
            [sys.executable, "-B", "-c", code], cwd=Path(__file__).resolve().parents[1],
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
