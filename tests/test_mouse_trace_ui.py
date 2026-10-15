"""Real Qt board capture with unchanged engine/Replay/gesture authorities."""

import os
import unittest
from unittest.mock import Mock, patch

from core_engine import Action, GameStatus, MinesweeperEngine
from mouse_trace import MouseTraceRecorder
from replay_model import ReplayBoard, ReplayData
from replay_player import ReplayPlayer
from tests.ui_settings import isolate_ui_settings

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PyQt5.QtCore import QEvent, QPoint, QPointF, Qt
    from PyQt5.QtGui import QMouseEvent
    from PyQt5.QtTest import QSignalSpy, QTest
    from PyQt5.QtWidgets import QApplication, QWidget
except ImportError:
    QApplication = None
else:
    from ui_manager import ChordMode, MinesweeperUI


@unittest.skipIf(QApplication is None, "PyQt5 unavailable")
class MouseTraceUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.settings = isolate_ui_settings(self)
        worker = patch.object(MinesweeperUI, "_ensure_zini_metric_job")
        worker.start()
        self.addCleanup(worker.stop)
        self.engine = MinesweeperEngine(5, 5, 3)
        self.engine.reset_with_mines(5, 5, 3, {(1, 1), (3, 1), (3, 3)})
        self.ui = MinesweeperUI(self.engine)
        self.addCleanup(self.close_ui)
        self.clock = Mock(return_value=1_000_000_000)
        self.install_recorder()
        self.ui.show()
        self.ui.activateWindow()
        self.app.processEvents()
        self.held = Qt.NoButton
        self.receiver = None
        # Qt remembers the last global pointer position across test windows.
        self.hover(self.outside())

    def close_ui(self):
        self.ui._stop_timer()
        self.ui._stop_replay_autoplay()
        self.ui.close()
        self.ui.deleteLater()
        self.app.processEvents()

    def install_recorder(self):
        self.recorder = MouseTraceRecorder(self.engine.width, self.engine.height, clock_ns=self.clock)
        self.ui._mouse_trace_recorder = self.recorder

    def point(self, target):
        if isinstance(target, QPoint):
            return target
        button = self.ui._buttons[target]
        return button.mapToGlobal(button.rect().center())

    def outside(self):
        return self.ui.scroll_area.viewport().mapToGlobal(QPoint(-8, -8))

    def send(self, kind, target, button=Qt.NoButton, receiver=None):
        if kind == QEvent.MouseButtonPress:
            if not self.held:
                self.receiver = receiver or self.ui._buttons[target]
            self.held |= button
        elif kind == QEvent.MouseButtonRelease:
            self.held &= ~button
        receiver = receiver or self.receiver
        global_pos = self.point(target)
        event = QMouseEvent(kind, QPointF(receiver.mapFromGlobal(global_pos)),
                            QPointF(global_pos), button, Qt.MouseButtons(self.held), Qt.NoModifier)
        self.app.sendEvent(receiver, event)

    def press(self, target, button=Qt.LeftButton):
        self.send(QEvent.MouseButtonPress, target, button)

    def release(self, target, button=Qt.LeftButton, receiver=None):
        self.send(QEvent.MouseButtonRelease, target, button, receiver)

    def click(self, target=(0, 0), button=Qt.LeftButton):
        self.press(target, button)
        self.release(target, button)

    def hover(self, target):
        # Exercise QWindow routing, not direct calls to the capture helper.
        QTest.mouseMove(self.ui.windowHandle(), self.ui.mapFromGlobal(self.point(target)))
        self.app.processEvents()

    def points(self):
        data = self.recorder.snapshot()
        return tuple(p for s in data.segments for p in s.points) if data else ()

    def markers(self):
        return tuple(p for p in self.points() if p.replay_event_index is not None)

    def assert_last_position(self, target):
        expected = self.ui.board_container.mapFromGlobal(self.point(target))
        point = self.points()[-1]
        self.assertEqual((point.x, point.y), (expected.x(), expected.y()))

    def test_pre_first_action_hover_and_press_do_not_start_or_read_clock(self):
        for target in ((0, 0), (1, 0), (2, 0)):
            self.hover(target)
        self.press((2, 0))
        self.send(QEvent.MouseMove, (3, 0))
        self.assertIsNone(self.recorder.snapshot())
        self.clock.assert_not_called()
        self.assertEqual(self.ui._replay_recorder.events, ())
        self.release((3, 0))
        self.assertEqual(len(self.points()), 1)
        self.assert_last_position((3, 0))
        self.assertEqual((self.points()[0].elapsed_us, self.points()[0].replay_event_index), (0, 0))

    def test_first_open_and_first_flag_start_from_observed_release(self):
        for button, action, target in ((Qt.LeftButton, "OPEN", (0, 0)),
                                       (Qt.RightButton, "FLAG", (1, 1))):
            with self.subTest(action=action):
                self.ui.on_reset()
                self.install_recorder()
                self.click(target, button)
                self.assertTrue(self.engine.get_board_snapshot().mines_placed)
                self.assertEqual(self.ui._replay_recorder.events[0].action, action)
                self.assertEqual(len(self.points()), 1)
                self.assertEqual(self.points()[0].elapsed_us, 0)
                self.assert_last_position(target)

    def test_qwindow_no_button_hover_after_start_is_sampled_without_gameplay(self):
        self.click()
        before = self.ui._replay_recorder.events
        counts = self.engine.get_counter_snapshot()
        self.clock.return_value += 123_000
        self.hover((2, 0))
        self.assert_last_position((2, 0))
        self.assertEqual(self.points()[-1].elapsed_us, 123)
        self.assertEqual(self.ui._replay_recorder.events, before)
        self.assertEqual(self.engine.get_counter_snapshot(), counts)
        self.assertEqual(self.ui._mouse_preview, set())
        self.assertEqual(len(self.recorder.snapshot().segments), 1)

    def test_first_release_origin_precedes_engine_zini_and_replay_processing(self):
        for button, target in ((Qt.LeftButton, (0, 0)), (Qt.RightButton, (1, 1))):
            with self.subTest(button=button):
                self.ui.on_reset()
                self.engine.reset_with_mines(5, 5, 3, {(1, 1), (3, 1), (3, 3)})
                self.install_recorder()
                self.hover(self.outside())
                step = self.engine.step
                record_event = self.ui._replay_recorder.record_event

                def advance_before_commit():
                    self.clock.assert_called_once_with()
                    self.assertFalse(self.recorder.started)
                    self.assertIsNone(self.recorder.snapshot())
                    self.clock.return_value += 1_000_000_000

                def delayed_step(*args, **kwargs):
                    advance_before_commit()
                    return step(*args, **kwargs)

                def delayed_replay_append(*args, **kwargs):
                    advance_before_commit()
                    return record_event(*args, **kwargs)

                self.press(target, button)
                self.clock.reset_mock()
                with patch.object(self.engine, "step", side_effect=delayed_step), \
                        patch.object(self.ui, "_ensure_zini_metric_job", side_effect=advance_before_commit), \
                        patch.object(self.ui._replay_recorder, "record_event", side_effect=delayed_replay_append):
                    self.release(target, button)
                self.clock.assert_called_once_with()
                self.assertEqual((self.markers()[0].elapsed_us, self.markers()[0].replay_event_index), (0, 0))
                self.clock.return_value += 17_000
                self.hover((4, 0))
                # Includes all three seconds of processing, not just 17 us
                # since completion of the first action.
                self.assertEqual(self.points()[-1].elapsed_us, 3_000_017)

    def test_later_release_marker_uses_observation_time_before_slow_action(self):
        self.click()
        self.press((0, 0))
        self.clock.return_value += 123_456_000
        self.clock.reset_mock()
        step = self.engine.step
        before = self.markers()

        def delayed_step(*args, **kwargs):
            self.clock.assert_called_once_with()
            self.assertEqual(self.markers(), before)
            self.clock.return_value += 4_000_000_000
            return step(*args, **kwargs)

        with patch.object(self.engine, "step", side_effect=delayed_step):
            self.release((2, 0))
        self.clock.assert_called_once_with()
        self.assertEqual((self.markers()[-1].elapsed_us, self.markers()[-1].replay_event_index), (123_456, 1))
        self.assert_last_position((2, 0))
        self.clock.return_value += 42_000
        self.hover((4, 0))
        self.assertEqual(self.points()[-1].elapsed_us, 4_123_498)

    def test_observed_release_requires_action_commit_and_successful_replay_append(self):
        for started in (False, True):
            for failure in ("action", "replay"):
                with self.subTest(started=started, failure=failure):
                    self.ui.on_reset()
                    self.engine.reset_with_mines(5, 5, 3, {(1, 1), (3, 1), (3, 3)})
                    self.install_recorder()
                    self.hover(self.outside())
                    if started:
                        self.click()
                    self.press((0, 0))
                    self.clock.return_value += 12_000
                    self.clock.reset_mock()
                    before = self.markers()
                    step = self.engine.step
                    record_event = self.ui._replay_recorder.record_event

                    def delayed_step(*args, **kwargs):
                        self.clock.assert_called_once_with()
                        self.assertEqual(self.markers(), before)
                        self.clock.return_value += 80_000_000
                        if failure == "action":
                            return None, None, None, None, {}  # No committed engine action.
                        return step(*args, **kwargs)

                    def delayed_replay_append(*args, **kwargs):
                        self.clock.assert_called_once_with()
                        self.clock.return_value += 40_000_000
                        if failure == "replay":
                            raise ValueError("not appended")
                        return record_event(*args, **kwargs)

                    with patch.object(self.engine, "step", side_effect=delayed_step), \
                            patch.object(self.ui._replay_recorder, "record_event", side_effect=delayed_replay_append), \
                            patch("builtins.print"):
                        self.release((2, 0))
                    self.clock.assert_called_once_with()
                    self.assertEqual(self.markers(), before)
                    self.assertEqual(self.recorder.started, started)
                    if not started:
                        self.assertIsNone(self.recorder.snapshot())
                        # A discarded candidate must not set the next origin.
                        self.click((4, 0))
                        self.assertEqual(self.markers()[0].elapsed_us, 0)
                        self.clock.return_value += 7_000
                        self.hover((3, 0))
                        self.assertEqual(self.points()[-1].elapsed_us, 7)
                    elif failure == "replay":
                        self.assertEqual(self.points()[-1].elapsed_us, 12)
                        self.assertIsNone(self.points()[-1].replay_event_index)

    def test_held_motion_preview_and_release_target_are_preserved(self):
        self.click()
        self.press((2, 0))
        self.send(QEvent.MouseMove, (4, 0))
        self.assertEqual(self.ui._mouse_preview, {(4, 0)})
        self.assert_last_position((4, 0))
        self.release((4, 0))
        self.assertEqual(self.ui._mouse_preview, set())
        self.assertEqual([(e.action, e.x, e.y) for e in self.ui._replay_recorder.events],
                         [("OPEN", 0, 0), ("OPEN", 4, 0)])
        self.assertEqual(len(self.recorder.snapshot().segments), 1)
        self.assertEqual([p.replay_event_index for p in self.markers()], [0, 1])

    def test_release_without_move_records_destination_and_same_position_actions(self):
        self.press((0, 0))
        self.release((2, 0))
        self.assert_last_position((2, 0))
        self.assertEqual(len(self.points()), 1)
        self.clock.return_value += 25_000
        self.click((2, 0), Qt.RightButton)  # Existing wasted FLAG still commits.
        self.assertEqual(len(self.markers()), 2)
        self.assertEqual(self.markers()[1].elapsed_us, 25)
        self.assertEqual(len(self.recorder.snapshot().segments), 1)

    def test_same_origin_both_is_one_chord_event_and_one_marker(self):
        self.click()
        self.click((1, 1), Qt.RightButton)
        self.ui.on_chord_mode_changed(ChordMode.BOTH_CLICK)
        before = len(self.ui._replay_recorder.events)
        self.press((0, 0))
        self.press((0, 0), Qt.RightButton)
        self.release((0, 0), Qt.RightButton)
        self.release((0, 0))
        self.assertEqual(len(self.ui._replay_recorder.events), before + 1)
        self.assertEqual(self.ui._replay_recorder.events[-1].action, "CHORD")
        self.assertEqual([p.replay_event_index for p in self.markers()], list(range(before + 1)))

    def test_untimed_first_chord_does_not_start_trace(self):
        self.press((0, 0))
        self.press((0, 0), Qt.RightButton)
        self.release((0, 0), Qt.RightButton)
        self.release((0, 0))
        self.assertEqual(self.ui._replay_recorder.events[0].action, "CHORD")
        self.assertIsNone(self.recorder.snapshot())
        self.assertFalse(self.recorder.started)  # Observing a release is not starting a trace.
        self.click()
        self.assertEqual(self.points()[0].replay_event_index, 1)

    def test_new_flag_suppressed_left_release_has_no_marker(self):
        self.click()
        self.press((2, 0))
        self.send(QEvent.MouseMove, (1, 1))
        self.press((1, 1), Qt.RightButton)
        self.release((1, 1), Qt.RightButton)
        before = self.markers()
        self.release((1, 1))
        self.assertEqual(self.markers(), before)
        self.assertEqual([e.action for e in self.ui._replay_recorder.events], ["OPEN", "FLAG"])

    def test_independent_button_releases_keep_distinct_action_links(self):
        self.click()
        self.press((2, 0))
        self.send(QEvent.MouseMove, (1, 1))
        self.press((1, 1), Qt.RightButton)
        self.release((1, 1), Qt.RightButton)
        self.send(QEvent.MouseMove, (4, 0))
        self.release((4, 0))
        self.assertEqual([e.action for e in self.ui._replay_recorder.events], ["OPEN", "FLAG", "OPEN"])
        self.assertEqual([p.replay_event_index for p in self.markers()], [0, 1, 2])

    def test_hover_exit_reentry_and_blank_viewport_create_gaps(self):
        self.click()
        self.hover((2, 0))
        count = len(self.points())
        self.hover(self.outside())
        self.assertEqual(len(self.points()), count)
        self.hover((4, 0))
        self.assertEqual(len(self.recorder.snapshot().segments), 2)
        # The small board does not fill the viewport. Blank space is not board.
        blank = self.ui.board_container.mapToGlobal(QPoint(self.ui.board_container.width() + 8, 10))
        self.assertTrue(self.ui.scroll_area.viewport().rect().contains(
            self.ui.scroll_area.viewport().mapFromGlobal(blank)))
        self.hover(blank)
        self.hover((2, 0))
        self.assertEqual(len(self.recorder.snapshot().segments), 3)

    def test_grabbed_exit_reentry_and_outside_release_never_link_outside(self):
        self.click()
        self.press((2, 0))
        self.send(QEvent.MouseMove, self.outside())
        self.send(QEvent.MouseMove, (4, 0))
        self.assertEqual(len(self.recorder.snapshot().segments), 2)
        before = self.markers()
        self.release(self.outside())
        self.assertEqual(self.markers(), before)
        self.assertTrue(all(0 <= p.x < 140 and 0 <= p.y < 140 for p in self.points()))

    def test_scroll_breaks_and_retains_board_local_coordinates(self):
        self.ui._rebuild_game(50, 50, 10)
        self.engine.reset_with_mines(50, 50, 10, {(x, 1) for x in range(10)})
        self.install_recorder()
        self.ui.resize(1000, 650)
        self.app.processEvents()
        self.click()
        before = self.recorder.snapshot()
        self.ui.scroll_area.horizontalScrollBar().setValue(280)
        self.ui.scroll_area.verticalScrollBar().setValue(280)
        self.app.processEvents()
        self.assertEqual(self.recorder.snapshot(), before)
        self.hover((12, 11))
        self.assertEqual(len(self.recorder.snapshot().segments), 2)
        self.assert_last_position((12, 11))
        self.assertGreater(self.points()[-1].x, 12 * 28)
        self.assertGreater(self.points()[-1].y, 11 * 28)
        # Grab-delivered coordinates on clipped cells are not captured.
        self.press((12, 11))
        count = len(self.points())
        self.send(QEvent.MouseMove, (0, 0))
        self.assertEqual(len(self.points()), count)
        self.release(self.outside())

    def test_live_cell_size_change_keeps_trace_and_begins_new_geometry_segment(self):
        self.click()
        old = self.recorder.snapshot()
        self.ui.on_cell_size_changed(60)
        self.app.processEvents()
        self.assertIs(self.ui._mouse_trace_recorder, self.recorder)
        self.hover((2, 0))
        data = self.recorder.snapshot()
        self.assertEqual(data.segments[0], old.segments[0])
        self.assertEqual([s.cell_size for s in data.segments], [28, 60])
        self.assert_last_position((2, 0))

    def test_reset_rebuild_and_custom_difficulty_start_empty_sessions(self):
        for transition in (self.ui.on_reset,
                           lambda: self.ui.on_difficulty_changed("초급 (9x9, 10)"),
                           lambda: self.ui._rebuild_game(7, 4, 3),
                           lambda: self.ui.on_difficulty_changed("커스텀")):
            with self.subTest(transition=transition):
                self.install_recorder()
                self.click((0, 0), Qt.RightButton)
                self.assertIsNotNone(self.recorder.snapshot())
                with patch.object(self.ui, "_ask_custom_dimensions", return_value=(8, 6, 4)):
                    transition()
                current = self.ui._mouse_trace_recorder
                self.assertIsNot(current, self.recorder)
                self.assertIsNone(current.snapshot())
                self.assertEqual((current.width, current.height), (self.engine.width, self.engine.height))
                self.assertTrue(current.eligible)
                self.app.processEvents()

    def test_stale_releases_cannot_start_new_session(self):
        self.press((0, 0))
        old = self.receiver
        self.ui._rebuild_game(5, 5, 3)
        self.install_recorder()
        self.release((0, 0), receiver=old)
        self.release((1, 0), receiver=self.ui._buttons[(1, 0)])
        self.assertIsNone(self.recorder.snapshot())
        self.assertEqual(self.ui._replay_recorder.events, ())

    def test_replay_entry_discards_live_capture_and_exit_resets(self):
        self.click()
        self.ui._enter_replay_mode(ReplayPlayer(ReplayData(ReplayBoard(2, 1, 1, {(1, 0)}), ())))
        self.assertFalse(self.recorder.eligible)
        self.assertIsNone(self.recorder.snapshot())
        self.hover((0, 0))
        self.click((0, 0))
        self.assertIsNone(self.recorder.snapshot())
        self.ui._exit_replay_mode()
        self.assertTrue(self.ui._mouse_trace_recorder.eligible)
        self.assertIsNone(self.ui._mouse_trace_recorder.snapshot())

    def test_terminal_action_is_linked_before_refresh_and_capture_freezes(self):
        for target, status in (((0, 0), GameStatus.WON), ((1, 0), GameStatus.LOST)):
            with self.subTest(status=status):
                self.ui._rebuild_game(2, 1, 1)
                self.engine.reset_with_mines(2, 1, 1, {(1, 0)})
                self.install_recorder()
                self.app.processEvents()
                refresh = self.ui._refresh_live_board

                def check_refresh(*args, **kwargs):
                    self.assertTrue(self.recorder.frozen)
                    self.assertEqual(self.markers()[-1].replay_event_index, 0)
                    refresh(*args, **kwargs)

                with patch.object(self.ui, "_refresh_live_board", side_effect=check_refresh):
                    self.click(target)
                self.assertEqual(self.engine.status, status)
                before = self.recorder.snapshot()
                events = self.ui._replay_recorder.events
                self.hover((1, 0))
                self.click((1, 0))
                self.assertEqual(self.recorder.snapshot(), before)
                self.assertEqual(self.ui._replay_recorder.events, events)
                self.assertEqual(len(self.markers()), 1)  # No victory auto-flag marker.

    def test_hide_show_deactivate_and_board_hide_break_continuity(self):
        self.click()
        self.ui.hide()
        before = self.recorder.snapshot()
        self.send(QEvent.MouseMove, (2, 0), receiver=self.ui._buttons[(2, 0)])
        self.assertEqual(self.recorder.snapshot(), before)
        self.ui.show()
        self.app.setActiveWindow(self.ui)
        self.app.processEvents()
        self.assertTrue(self.ui.isActiveWindow())
        hover_events = QSignalSpy(self.ui._buttons[(4, 0)].mouse_input)
        self.hover((4, 0))
        self.assertGreater(len(hover_events), 0)
        self.assertEqual(len(self.recorder.snapshot().segments), 2)
        other = QWidget()
        try:
            other.show()
            other.activateWindow()
            self.app.processEvents()
            before = self.recorder.snapshot()
            self.send(QEvent.MouseMove, (3, 0), receiver=self.ui._buttons[(3, 0)])
            self.assertEqual(self.recorder.snapshot(), before)
            self.ui.activateWindow()
            self.app.processEvents()
            self.hover((2, 0))
            self.assertEqual(len(self.recorder.snapshot().segments), 3)
        finally:
            other.close()
            other.deleteLater()
        self.ui.board_container.hide()
        self.ui.board_container.show()
        self.app.processEvents()
        self.hover((4, 0))
        self.assertEqual(len(self.recorder.snapshot().segments), 4)

    def test_close_freezes_capture(self):
        self.click()
        self.ui.close()
        self.assertTrue(self.recorder.frozen)

    def test_auto_enable_without_execution_keeps_trace(self):
        self.ui.on_reset()
        self.install_recorder()
        self.ui.simple_auto_checkbox.setChecked(True)
        self.assertTrue(self.ui._simple_auto_pending)
        self.assertTrue(self.recorder.eligible)
        self.ui.simple_auto_checkbox.setChecked(False)
        self.assertTrue(self.recorder.eligible)
        self.assertIsNone(self.recorder.snapshot())

    def test_first_executed_auto_invalidates_human_capture_until_reset(self):
        self.click()
        self.ui.simple_auto_checkbox.setChecked(True)
        self.ui.allow_guess_checkbox.setChecked(True)
        self.assertTrue(self.recorder.eligible)
        self.assertTrue(self.ui._simple_auto_pending)
        self.ui._simple_auto_timer.timeout.emit()
        self.assertFalse(self.recorder.eligible)
        self.assertIsNone(self.recorder.snapshot())
        self.assertEqual(self.ui._replay_recorder.source_type, "human")
        self.ui.simple_auto_checkbox.setChecked(False)
        self.hover((4, 0))
        self.click((4, 0))
        self.assertIsNone(self.recorder.snapshot())
        self.ui.on_reset()
        self.assertTrue(self.ui._mouse_trace_recorder.eligible)

    def test_failed_auto_step_does_not_invalidate_trace(self):
        self.click()
        self.ui.simple_auto_checkbox.setChecked(True)
        self.ui.allow_guess_checkbox.setChecked(True)
        self.assertTrue(self.ui._simple_auto_pending)
        with patch.object(self.engine, "step", side_effect=RuntimeError("not executed")) as step:
            self.ui._simple_auto_timer.timeout.emit()
        step.assert_called_once()
        self.assertTrue(self.recorder.eligible)
        self.assertIsNotNone(self.recorder.snapshot())

    def test_failed_replay_append_does_not_start_or_invent_action_reference(self):
        with patch.object(self.ui._replay_recorder, "record_event", side_effect=ValueError("not appended")), \
                patch("builtins.print"):
            self.click()
        self.assertIsNone(self.recorder.snapshot())
        self.assertEqual(self.ui._replay_recorder.events, ())

    def test_direct_action_slot_cannot_reuse_previous_release_position(self):
        self.ui.on_left_click(0, 0)
        self.assertIsNone(self.recorder.snapshot())
        self.click((2, 0))
        self.assertEqual(self.markers()[0].replay_event_index, 1)
        self.ui.on_right_click(1, 1)
        self.assertEqual(len(self.markers()), 1)

    def test_release_callback_cannot_resample_old_coordinates_in_new_geometry(self):
        self.click()
        target = self.ui._buttons[(2, 0)]
        target.left_clicked.connect(lambda _x, _y: self.ui.on_cell_size_changed(60))
        expected = self.ui.board_container.mapFromGlobal(self.point((2, 0)))
        self.press((0, 0))
        self.release((2, 0))
        data = self.recorder.snapshot()
        self.assertEqual([s.cell_size for s in data.segments], [28])
        self.assertEqual(len(self.points()), 2)
        self.assertEqual((self.markers()[-1].x, self.markers()[-1].y),
                         (expected.x(), expected.y()))
        self.assertEqual([p.replay_event_index for p in self.markers()], [0, 1])

    def test_subpixel_release_geometry_is_not_rounded_or_replaced_by_cell_center(self):
        button = self.ui._buttons[(0, 0)]
        self.press((0, 0))
        local = QPointF(4.25, 7.75)
        origin = button.mapToGlobal(QPoint(0, 0))
        event = QMouseEvent(QEvent.MouseButtonRelease, local,
                            QPointF(origin) + local, Qt.LeftButton, Qt.NoButton, Qt.NoModifier)
        self.app.sendEvent(button, event)
        self.held = Qt.NoButton
        self.assertEqual((self.points()[0].x, self.points()[0].y), (4.25, 7.75))


if __name__ == "__main__":
    unittest.main()
