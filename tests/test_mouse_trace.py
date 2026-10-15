"""Pure capture contract: fake clock only, no Qt, gameplay, or file I/O."""

from dataclasses import FrozenInstanceError
import gc
import unittest
import weakref
from unittest.mock import Mock

from mouse_trace import MouseTraceData, MouseTracePoint, MouseTraceRecorder, MouseTraceSegment


class MouseTraceTests(unittest.TestCase):
    def setUp(self):
        self.clock = Mock(return_value=10_000_000)
        self.recorder = MouseTraceRecorder(3, 2, clock_ns=self.clock)

    def start(self, index=0):
        return self.recorder.record_action(10.5, 15, 28, index)

    def points(self):
        return tuple(p for s in self.recorder.snapshot().segments for p in s.points)

    def test_hover_before_first_committed_action_never_reads_clock_or_records(self):
        self.assertTrue(self.recorder.eligible)
        self.assertFalse(self.recorder.started)
        for x in range(20):
            self.recorder.record_position(x, 10, 28)
        self.recorder.break_segment()
        self.clock.assert_not_called()
        self.assertIsNone(self.recorder.snapshot())

    def test_first_action_starts_at_zero_and_retains_actual_event_index(self):
        point = self.start(index=3)
        self.assertEqual(point, MouseTracePoint(0, 10.5, 15, 3))
        self.assertTrue(self.recorder.started)
        self.clock.assert_called_once_with()
        self.assertEqual(self.points(), (point,))

    def test_observing_a_candidate_does_not_start_or_change_trace(self):
        self.recorder.observation_time_ns()
        self.assertFalse(self.recorder.started)
        self.assertIsNone(self.recorder.snapshot())
        self.clock.return_value += 5_000_000
        self.start()
        before = self.recorder.snapshot()
        self.clock.return_value += 2_000_000
        self.recorder.observation_time_ns()  # An uncommitted candidate is discarded.
        self.assertEqual(self.recorder.snapshot(), before)

    def test_first_observed_release_anchors_time_despite_delayed_link(self):
        observed_ns = self.recorder.observation_time_ns()
        self.clock.return_value += 2_000_000
        self.clock.reset_mock()
        first = self.recorder.record_action(10.5, 15, 28, 0, observed_ns=observed_ns)
        self.assertEqual(first.elapsed_us, 0)
        self.clock.assert_not_called()  # Linking must not read completion time.
        self.clock.return_value += 7_000
        movement = self.recorder.record_position(11, 15, 28)
        self.assertEqual(movement.elapsed_us, 2_007)

    def test_later_action_preserves_release_time_across_processing_delay(self):
        self.start()
        self.clock.return_value += 45_123
        observed_ns = self.recorder.observation_time_ns()
        self.clock.return_value += 3_000_000
        self.clock.reset_mock()
        point = self.recorder.record_action(20, 15, 28, 1, observed_ns=observed_ns)
        self.assertEqual((point.elapsed_us, point.replay_event_index), (45, 1))
        self.clock.assert_not_called()
        movement = self.recorder.record_position(21, 15, 28)
        self.assertEqual(movement.elapsed_us, 3_045)

    def test_unlinked_release_position_can_keep_its_observation_time(self):
        self.start()
        self.clock.return_value += 12_000
        observed_ns = self.recorder.observation_time_ns()
        self.clock.return_value += 1_000_000
        point = self.recorder.record_position(20, 15, 28, observed_ns=observed_ns)
        self.assertEqual(point, MouseTracePoint(12, 20, 15))

    def test_invalid_or_out_of_order_observation_times_rejected_atomically(self):
        self.start()
        before = self.recorder.snapshot()
        for value in (9_999_999, True, 1.5, "10000000"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.recorder.record_action(20, 15, 28, 1, observed_ns=value)
            self.assertEqual(self.recorder.snapshot(), before)

    def test_relative_microseconds_equal_timestamps_and_submicrosecond_truncation(self):
        self.start()
        self.clock.return_value += 123_456
        self.recorder.record_position(11, 15, 28)
        self.clock.return_value += 100
        self.recorder.record_position(12, 15, 28)
        self.recorder.record_action(12, 15, 28, 1)
        self.assertEqual([p.elapsed_us for p in self.points()], [0, 123, 123, 123])

    def test_dedup_only_consecutive_positions_and_preserve_action_sample(self):
        self.start()
        self.clock.return_value += 2_000
        self.assertIsNone(self.recorder.record_position(10.5, 15, 28))
        self.recorder.record_action(10.5, 15, 28, 1)
        self.recorder.record_position(11, 15, 28)
        self.recorder.record_position(10.5, 15, 28)
        points = self.points()
        self.assertEqual(len(points), 4)
        self.assertEqual([p.replay_event_index for p in points], [0, 1, None, None])
        self.assertEqual(points[1].elapsed_us, 2)

    def test_break_keeps_singleton_and_reentry_even_at_same_position(self):
        first = self.start()
        self.recorder.break_segment()
        self.recorder.break_segment()
        self.clock.return_value += 5_000
        self.recorder.record_position(first.x, first.y, 28)
        data = self.recorder.snapshot()
        self.assertEqual([len(s.points) for s in data.segments], [1, 1])
        self.assertEqual(data.segments[1].points[0].elapsed_us, 5)

    def test_cell_size_change_starts_segment_without_rewriting_pixels(self):
        self.start()
        self.clock.return_value += 1_000
        self.recorder.record_position(100, 60, 60)
        data = self.recorder.snapshot()
        self.assertEqual([s.cell_size for s in data.segments], [28, 60])
        self.assertEqual(data.segments[0].points[0].x, 10.5)
        self.assertEqual(data.segments[1].points[0].x, 100)

    def test_snapshot_is_immutable_detached_and_survives_reset_invalidation(self):
        self.start()
        snapshot = self.recorder.snapshot()
        with self.assertRaises(FrozenInstanceError):
            snapshot.width = 10
        with self.assertRaises(FrozenInstanceError):
            snapshot.segments[0].points[0].x = 9
        self.recorder.record_position(20, 20, 28)
        self.recorder.record_action(20, 20, 28, 1)
        self.recorder.invalidate()
        self.recorder.reset(2, 2)
        self.recorder.record_action(1, 1, 10, 0)
        self.assertEqual(snapshot, MouseTraceData(3, 2, (
            MouseTraceSegment(28, (MouseTracePoint(0, 10.5, 15, 0),)),
        )))

    def test_public_containers_copy_input_lists(self):
        points = [MouseTracePoint(0, 1, 1, 0)]
        segment = MouseTraceSegment(10, points)
        segments = [segment]
        data = MouseTraceData(2, 2, segments)
        points.clear()
        segments.clear()
        self.assertEqual(len(data.segments[0].points), 1)
        self.assertIsInstance(data.segments, tuple)
        self.assertIsInstance(segment.points, tuple)

    def test_freeze_retains_terminal_marker_and_reads_no_more_clock(self):
        self.start()
        self.recorder.record_action(40, 20, 28, 1)
        self.recorder.freeze()
        before = self.recorder.snapshot()
        self.clock.reset_mock()
        self.recorder.record_position(20, 20, 28)
        self.recorder.record_action(20, 20, 28, 2)
        self.clock.assert_not_called()
        self.assertTrue(self.recorder.frozen)
        self.assertEqual(self.recorder.snapshot(), before)

    def test_invalidate_discards_and_reset_restores_eligibility(self):
        self.start()
        self.recorder.invalidate()
        self.assertFalse(self.recorder.eligible)
        self.assertIsNone(self.recorder.snapshot())
        self.recorder.record_action(1, 1, 10, 1)
        self.assertIsNone(self.recorder.snapshot())
        self.recorder.reset(2, 3)
        self.assertTrue(self.recorder.eligible)
        self.assertFalse(self.recorder.frozen)
        self.assertIsNone(self.recorder.snapshot())
        self.recorder.record_action(1, 1, 10, 0)
        self.assertEqual((self.recorder.snapshot().width, self.recorder.snapshot().height), (2, 3))

    def test_unstarted_freeze_has_no_empty_trace(self):
        self.recorder.freeze()
        self.assertIsNone(self.recorder.snapshot())
        self.assertIsNone(self.start())

    def test_invalid_dimensions_and_reset_are_rejected_atomically(self):
        self.start()
        before = self.recorder.snapshot()
        for value in (0, -1, True, 2.5, "2", None):
            for dimensions in ((value, 2), (2, value)):
                with self.subTest(dimensions=dimensions), self.assertRaises(ValueError):
                    MouseTraceRecorder(*dimensions)
                with self.assertRaises(ValueError):
                    self.recorder.reset(*dimensions)
                with self.assertRaises(ValueError):
                    MouseTraceData(*dimensions, before.segments)
        self.assertEqual(self.recorder.snapshot(), before)

    def test_invalid_cell_sizes(self):
        for value in (0, -1, True, 1.5, "28", None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    MouseTraceSegment(value, (MouseTracePoint(0, 1, 1, 0),))
                with self.assertRaises(ValueError):
                    self.recorder.record_action(1, 1, value, 0)
        self.clock.assert_not_called()
        self.assertIsNone(self.recorder.snapshot())

    def test_invalid_scalar_positions_and_half_open_board_bounds(self):
        for value in (-1, True, float("nan"), float("inf"), -float("inf"), "1", None):
            for xy in ((value, 1), (1, value)):
                with self.subTest(xy=xy), self.assertRaises(ValueError):
                    self.recorder.record_action(*xy, 28, 0)
        for xy in ((84, 1), (1, 56), (85, 60)):
            with self.subTest(xy=xy), self.assertRaises(ValueError):
                self.recorder.record_action(*xy, 28, 0)
            with self.assertRaises(ValueError):
                MouseTraceData(3, 2, (MouseTraceSegment(28, (MouseTracePoint(0, *xy, 0),)),))
        self.clock.assert_not_called()
        self.recorder.record_action(83.9, 55.9, 28, 0)

    def test_invalid_elapsed_times_and_event_indices(self):
        for value in (-1, True, 1.5, "1", None, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                MouseTracePoint(value, 1, 1)
            if value is not None:
                with self.assertRaises(ValueError):
                    MouseTracePoint(0, 1, 1, value)
            with self.assertRaises(ValueError):
                self.recorder.record_action(1, 1, 28, value)

    def test_duplicate_or_reversed_event_links_rejected_across_segments(self):
        self.start(index=3)
        self.recorder.break_segment()
        before = self.recorder.snapshot()
        for value in (3, 2):
            with self.assertRaises(ValueError):
                self.recorder.record_action(1, 1, 28, value)
            with self.assertRaises(ValueError):
                MouseTraceData(3, 2, before.segments + (
                    MouseTraceSegment(28, (MouseTracePoint(1, 1, 1, value),)),
                ))
        self.assertEqual(self.recorder.snapshot(), before)

    def test_decreasing_segment_and_trace_times_rejected(self):
        first = MouseTracePoint(0, 1, 1, 0)
        with self.assertRaises(ValueError):
            MouseTraceSegment(28, (first, MouseTracePoint(2, 1, 1), MouseTracePoint(1, 1, 1)))
        with self.assertRaises(ValueError):
            MouseTraceData(3, 2, (
                MouseTraceSegment(28, (first, MouseTracePoint(2, 1, 1))),
                MouseTraceSegment(28, (MouseTracePoint(1, 1, 1),)),
            ))

    def test_empty_or_unanchored_public_data_rejected(self):
        for points in ((), ("not a point",)):
            with self.assertRaises(ValueError):
                MouseTraceSegment(28, points)
        for segments in ((), ("not a segment",),
                         (MouseTraceSegment(28, (MouseTracePoint(1, 1, 1, 0),)),),
                         (MouseTraceSegment(28, (MouseTracePoint(0, 1, 1),)),)):
            with self.assertRaises(ValueError):
                MouseTraceData(3, 2, segments)

    def test_backwards_or_noninteger_clock_rejected_without_mutation(self):
        self.start()
        before = self.recorder.snapshot()
        for value in (9_999_999, True, 1.5, None):
            self.clock.return_value = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.recorder.record_position(20, 20, 28)
            self.assertEqual(self.recorder.snapshot(), before)

    def test_returned_point_is_immutable_but_not_retained_by_live_storage(self):
        point = self.start()
        reference = weakref.ref(point)
        with self.assertRaises(FrozenInstanceError):
            point.x = 0
        expected = MouseTracePoint(0, 10.5, 15, 0)
        del point
        gc.collect()
        self.assertIsNone(reference())
        self.assertEqual(self.points(), (expected,))

    def test_exact_stream_snapshot_and_v2_json_preserve_scalar_values(self):
        from replay_json import replay_data_to_dict
        from replay_model import ReplayBoard, ReplayData, ReplayEvent

        first = self.start(index=1)  # A pre-start CHORD may already occupy 0.
        self.clock.return_value += 1_234_567
        self.assertEqual(self.recorder.record_position(12, 15.25, 28),
                         MouseTracePoint(1234, 12, 15.25))
        self.assertIsNone(self.recorder.record_position(12, 15.25, 28))
        observed = self.recorder.observation_time_ns()
        self.clock.return_value += 9_000_000
        self.assertEqual(self.recorder.record_action(12, 15.25, 28, 2, observed_ns=observed),
                         MouseTracePoint(1234, 12, 15.25, 2))
        self.recorder.break_segment()
        self.recorder.record_position(12, 15.25, 28)
        self.recorder.record_position(10.125, 11, 14)
        expected = MouseTraceData(3, 2, (
            MouseTraceSegment(28, (first, MouseTracePoint(1234, 12, 15.25),
                                   MouseTracePoint(1234, 12, 15.25, 2))),
            MouseTraceSegment(28, (MouseTracePoint(10234, 12, 15.25),)),
            MouseTraceSegment(14, (MouseTracePoint(10234, 10.125, 11),)),
        ))
        frozen = self.recorder.snapshot()
        self.assertEqual(frozen, expected)
        events = tuple(ReplayEvent(float(i), 0, 0, action)
                       for i, action in enumerate(("CHORD", "OPEN", "FLAG")))
        board = ReplayBoard(3, 2, 1, {(2, 1)})
        self.assertEqual(replay_data_to_dict(ReplayData(board, events, "human", 2, frozen)),
                         replay_data_to_dict(ReplayData(board, events, "human", 2, expected)))
        self.assertIs(type(frozen.segments[0].points[1].x), int)
        self.assertIs(type(frozen.segments[0].points[1].y), float)
        self.recorder.record_position(13, 12, 14)
        self.assertEqual(frozen, expected)

    def test_append_validation_is_atomic_including_private_session_state(self):
        for started in (False, True):
            self.recorder.reset(3, 2)
            if started:
                self.start()
                self.recorder.break_segment()
            before = (self.recorder.snapshot(), self.recorder._segment_open,
                      self.recorder._origin_ns, self.recorder._last_ns, self.recorder._last_event_index)
            candidates = [(-1, 2, 28, 1, 10_000_000), (True, 2, 28, 1, 10_000_000),
                          (float("nan"), 2, 28, 1, 10_000_000), (84, 2, 28, 1, 10_000_000),
                          (1, 2, 0, 1, 10_000_000), (1, 2, 28, True, 10_000_000),
                          (1, 2, 28, -1, 10_000_000), (1, 2, 28, 1, True),
                          (1, 2, 28, 1, 1.5)]
            if started:
                candidates += [(1, 2, 28, 0, 10_000_000), (1, 2, 28, 1, 9_999_999)]
            for x, y, size, index, timestamp in candidates:
                with self.subTest(started=started, values=(x, y, size, index, timestamp)):
                    with self.assertRaises(ValueError):
                        self.recorder.record_action(x, y, size, index, observed_ns=timestamp)
                    self.assertEqual((self.recorder.snapshot(), self.recorder._segment_open,
                                      self.recorder._origin_ns, self.recorder._last_ns,
                                      self.recorder._last_event_index), before)


if __name__ == "__main__":
    unittest.main()
