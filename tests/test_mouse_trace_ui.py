"""Real Qt board capture with unchanged engine/Replay/gesture authorities."""

import os
import json
from pathlib import Path
from dataclasses import replace
import unittest
from unittest.mock import Mock, patch

from core_engine import Action, GameStatus, MinesweeperEngine
from mouse_trace import MouseTraceData, MouseTracePoint, MouseTraceRecorder, MouseTraceSegment
from replay_model import ReplayBoard, ReplayData, ReplayEvent
from replay_player import ReplayPlayer
from replay_json import load_replay_json, replay_data_to_dict, save_replay_json
from replay_statistics import ReplayStatisticsAnalyzer
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
    from ui_manager import ChordMode, MinesweeperUI, REPLAY_MODE_INDEX, REPLAY_MODE_TIME


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

    def test_first_open_release_and_flag_press_start_at_zero(self):
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

    def test_prestart_gating_allows_only_first_flag_candidate_press(self):
        for checked in (True, False):
            with self.subTest(checked=checked):
                self.ui.on_reset()
                self.install_recorder()
                self.ui.mouse_trace_record_checkbox.setChecked(checked)
                self.clock.reset_mock()
                with patch.object(self.ui, "_mouse_trace_position", wraps=self.ui._mouse_trace_position) as position:
                    self.hover((1, 0))
                    self.press((2, 0))
                    self.send(QEvent.MouseMove, (3, 0))
                    position.assert_not_called()
                    self.clock.assert_not_called()
                    self.press((3, 0), Qt.RightButton)
                    position.assert_called_once()
                    self.clock.assert_called_once_with()
                    self.assertFalse(self.ui.mouse_trace_record_checkbox.isEnabled())
                    self.assertEqual(self.recorder.started, checked)
                    self.assertEqual(self.recorder.eligible, checked)
                    marker = self.markers()
                    if checked:
                        self.assertEqual(marker[0].elapsed_us, 0)
                        self.assert_last_position((3, 0))
                    self.clock.return_value += 1_000_000_000
                    self.release((4, 0), Qt.RightButton)
                    self.release((3, 0))
                    self.assertEqual(self.markers(), marker)

    def test_invalidated_and_frozen_movement_skip_trace_geometry(self):
        self.click()
        for stop in (self.recorder.freeze, self.recorder.invalidate):
            stop()
            with patch.object(self.ui, "_mouse_trace_position") as position:
                self.send(QEvent.MouseMove, (2, 0), receiver=self.ui._buttons[(2, 0)])
                position.assert_not_called()

    def test_consolidated_mapping_matches_original_qt_hit_test_and_float_bounds(self):
        def original(event):
            if self.ui._cell_at_mouse_position(event.globalPos()) is None:
                return None
            screen = event.screenPos()
            origin = self.ui.board_container.mapToGlobal(QPoint(0, 0))
            view = self.ui.scroll_area.viewport()
            view_origin = view.mapToGlobal(QPoint(0, 0))
            x, y = screen.x() - origin.x(), screen.y() - origin.y()
            if (0 <= x < self.engine.width * self.ui._cell_size
                    and 0 <= y < self.engine.height * self.ui._cell_size
                    and 0 <= screen.x() - view_origin.x() < view.width()
                    and 0 <= screen.y() - view_origin.y() < view.height()):
                return x, y
            return None

        for large in (False, True):
            if large:
                self.ui._rebuild_game(50, 50, 10)
                self.ui.resize(1000, 650)
                self.app.processEvents()
                self.ui.scroll_area.horizontalScrollBar().setValue(281)
                self.ui.scroll_area.verticalScrollBar().setValue(279)
                self.app.processEvents()
            self.ui._buttons[(2, 0)].setEnabled(False)
            self.ui._buttons[(3, 0)].hide()
            self.ui.mouse_trace_overlay.show()  # Transparent child must not change hit acceptance.
            board = self.ui.board_container
            origin = QPointF(board.mapToGlobal(QPoint(0, 0)))
            view = self.ui.scroll_area.viewport()
            xs = [-.75, -.25, 0, 4.25, 27.49, 27.51, 28, 60, 90,
                  board.width() - .75, board.width() - .25, board.width() + .25,
                  -board.x() - .25, -board.x() + .25,
                  -board.x() + view.width() - .25, -board.x() + view.width() + .25]
            ys = [-.75, -.25, 0, 7.75, 28.25, board.height() - .25,
                  -board.y() - .25, -board.y() + .25,
                  -board.y() + view.height() - .25, -board.y() + view.height() + .25]
            for x in xs:
                for y in ys:
                    event = QMouseEvent(QEvent.MouseMove, QPointF(x, y), origin + QPointF(x, y),
                                        Qt.NoButton, Qt.NoButton, Qt.NoModifier)
                    with self.subTest(large=large, x=x, y=y):
                        self.assertEqual(self.ui._mouse_trace_position(event), original(event))

    def test_started_dispatch_keeps_every_delivered_subpixel_sample(self):
        self.click((0, 0), Qt.RightButton)
        first = self.points()[0]
        events = self.ui._replay_recorder.events
        counters = self.engine.get_counter_snapshot()
        board_origin = QPointF(self.ui.board_container.mapToGlobal(QPoint(0, 0)))
        expected = [first]
        receiver = self.ui._buttons[(0, 0)]
        for i in range(1, 201):
            self.clock.return_value += 1000
            local = QPointF(10 + i / 4, 10 + i / 8)
            event = QMouseEvent(QEvent.MouseMove, local, board_origin + local,
                                Qt.NoButton, Qt.NoButton, Qt.NoModifier)
            self.app.sendEvent(receiver, event)
            expected.append(MouseTracePoint(i, event.screenPos().x() - board_origin.x(),
                                           event.screenPos().y() - board_origin.y()))
        self.assertEqual(self.points(), tuple(expected))
        self.assertEqual(self.ui._replay_recorder.events, events)
        self.assertEqual(self.engine.get_counter_snapshot(), counters)

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

    def test_first_action_observation_precedes_engine_zini_and_replay_processing(self):
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

                if button == Qt.LeftButton:
                    self.press(target, button)
                self.clock.reset_mock()
                with patch.object(self.engine, "step", side_effect=delayed_step), \
                        patch.object(self.ui, "_ensure_zini_metric_job", side_effect=advance_before_commit), \
                        patch.object(self.ui._replay_recorder, "record_event", side_effect=delayed_replay_append):
                    if button == Qt.LeftButton:
                        self.release(target, button)
                    else:
                        self.press(target, button)
                self.clock.assert_called_once_with()
                self.assertEqual((self.markers()[0].elapsed_us, self.markers()[0].replay_event_index), (0, 0))
                self.clock.return_value += 17_000
                self.hover((4, 0))
                # Includes all three seconds of processing, not just 17 us
                # since completion of the first action.
                self.assertEqual(self.points()[-1].elapsed_us, 3_000_017)
                if button == Qt.RightButton:
                    self.release(target, button)

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
                    if failure == "replay":
                        self.assertFalse(self.recorder.eligible)
                        self.assertIsNone(self.recorder.snapshot())
                        self.assertFalse(self.ui.mouse_trace_record_checkbox.isEnabled())
                        self.click((4, 0))
                        self.assertIsNone(self.recorder.snapshot())
                    else:
                        self.assertEqual(self.markers(), before)
                        self.assertEqual(self.recorder.started, started)
                        self.assertTrue(self.recorder.eligible)
                    if not started and failure == "action":
                        self.assertIsNone(self.recorder.snapshot())
                        # A discarded candidate must not set the next origin.
                        self.click((4, 0))
                        self.assertEqual(self.markers()[0].elapsed_us, 0)
                        self.clock.return_value += 7_000
                        self.hover((3, 0))
                        self.assertEqual(self.points()[-1].elapsed_us, 7)

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
        self.ui.on_chord_mode_changed(ChordMode.BOTH_CLICK)
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

    def test_flag_press_subpixels_time_and_release_delay_are_exact(self):
        self.clock.return_value = 2_000_000_000
        receiver = self.ui._buttons[(0, 0)]
        origin = QPointF(self.ui.board_container.mapToGlobal(QPoint(0, 0)))
        local = QPointF(4.25, 7.75)
        event = QMouseEvent(QEvent.MouseButtonPress, local, origin + local,
                            Qt.RightButton, Qt.RightButton, Qt.NoModifier)
        self.app.sendEvent(receiver, event)
        self.held, self.receiver = Qt.RightButton, receiver
        first = self.markers()[0]
        self.assertEqual((first.x, first.y, first.elapsed_us, first.replay_event_index), (4.25, 7.75, 0, 0))
        self.assertFalse(self.ui.mouse_trace_record_checkbox.isEnabled())
        self.clock.return_value += 9_000_000_000
        self.release((4, 0), Qt.RightButton)
        self.assertEqual(self.markers(), (first,))
        self.assert_last_position((4, 0))
        self.assertEqual(self.points()[-1].elapsed_us, 9_000_000)
        self.clock.return_value += 123_000
        step = self.engine.step
        def slow_step(*args, **kwargs):
            self.clock.return_value += 4_000_000_000
            return step(*args, **kwargs)
        with patch.object(self.engine, "step", side_effect=slow_step):
            self.press((1, 1), Qt.RightButton)
        marker = self.markers()[-1]
        self.assertEqual((marker.elapsed_us, marker.replay_event_index), (9_000_123, 1))
        self.assert_last_position((1, 1))
        self.release((2, 0), Qt.RightButton)
        self.assertEqual(self.markers()[-1], marker)
        data = self.ui._build_current_replay_data("test")
        self.assertEqual(replay_data_to_dict(data)["schema_version"], 2)
        path = Path(self.settings.fileName()).parent / "press-trace.json"
        save_replay_json(data, str(path))
        self.assertEqual(load_replay_json(str(path)), data)

    def test_chord_markers_use_the_committing_release_in_each_mode_and_order(self):
        for mode in (ChordMode.LEFT_CLICK, ChordMode.BOTH_CLICK):
            for first_press in (Qt.LeftButton, Qt.RightButton):
                for first_release in (Qt.LeftButton, Qt.RightButton):
                    with self.subTest(mode=mode, first_press=first_press, first_release=first_release):
                        self.ui.on_reset()
                        self.engine.reset_with_mines(5, 5, 3, {(1, 1), (3, 1), (3, 3)})
                        self.install_recorder()
                        self.click()
                        self.click((1, 1), Qt.RightButton)
                        self.ui.on_chord_mode_changed(mode)
                        other_press = Qt.RightButton if first_press == Qt.LeftButton else Qt.LeftButton
                        other_release = Qt.RightButton if first_release == Qt.LeftButton else Qt.LeftButton
                        self.press((0, 0), first_press)
                        self.press((0, 0), other_press)
                        before = len(self.markers())
                        self.clock.return_value += 101_000
                        self.release((0, 0), first_release)
                        commits_first = mode == ChordMode.BOTH_CLICK or first_release == Qt.LeftButton
                        self.assertEqual(len(self.markers()), before + int(commits_first))
                        self.clock.return_value += 203_000
                        self.release((0, 0), other_release)
                        self.assertEqual(len(self.markers()), before + 1)
                        marker = self.markers()[-1]
                        self.assertEqual(marker.elapsed_us, 101 if commits_first else 304)
                        self.assertEqual(self.ui._replay_recorder.events[marker.replay_event_index].action, "CHORD")

    def test_suppressed_mode_b_press_is_gated_before_start_and_sampled_after_start(self):
        self.ui.on_chord_mode_changed(ChordMode.BOTH_CLICK)
        with patch.object(self.ui, "_mouse_trace_position", wraps=self.ui._mouse_trace_position) as position:
            self.press((0, 0))
            self.send(QEvent.MouseMove, (2, 0))
            self.press((2, 0), Qt.RightButton)
            position.assert_not_called()
            self.clock.assert_not_called()
        self.assertIsNone(self.recorder.snapshot())
        self.assertEqual(self.ui._replay_recorder.events, ())
        self.release((2, 0), Qt.RightButton)
        self.release((2, 0))
        self.assertIsNone(self.recorder.snapshot())
        self.click((0, 0))
        before = len(self.points())
        for kind, target, button in ((QEvent.MouseButtonPress, (2, 0), Qt.LeftButton),
                                     (QEvent.MouseButtonPress, (3, 0), Qt.RightButton),
                                     (QEvent.MouseMove, (4, 0), Qt.NoButton),
                                     (QEvent.MouseButtonRelease, (2, 0), Qt.RightButton),
                                     (QEvent.MouseButtonRelease, (3, 0), Qt.LeftButton)):
            self.clock.return_value += 7_000
            self.send(kind, target, button)
            self.assert_last_position(target)
        points = self.points()[before:]
        self.assertEqual([p.elapsed_us for p in points], [7, 14, 21, 28, 35])
        self.assertEqual([p.replay_event_index for p in points], [None, None, None, 2, None])

    def test_flag_press_callback_cannot_reuse_context_after_reset_or_resize(self):
        for change in (self.ui.on_reset, lambda: self.ui.on_cell_size_changed(60)):
            with self.subTest(change=change):
                self.ui.on_reset()
                self.install_recorder()
                old_recorder = self.recorder
                target = self.ui._buttons[(0, 0)]
                def callback(_x, _y):
                    change()
                target.right_clicked.connect(callback)
                self.press((0, 0), Qt.RightButton)
                target.right_clicked.disconnect(callback)
                self.assertIsNone(self.ui._mouse_trace_observation)
                self.assertEqual(self.ui._mouse_buttons, Qt.NoButton)
                events = self.ui._replay_recorder.events
                self.release((2, 0), Qt.RightButton)
                self.assertEqual(self.ui._replay_recorder.events, events)
                self.assertEqual(len(tuple(p for seg in old_recorder.snapshot().segments for p in seg.points)), 1)

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
        self.assertTrue(self.ui.mouse_trace_record_checkbox.isEnabled())
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
        self.assertFalse(self.ui.mouse_trace_record_checkbox.isEnabled())
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

    def test_first_open_or_flag_replay_append_failure_prevents_later_trace_start(self):
        for button in (Qt.LeftButton, Qt.RightButton):
            with self.subTest(button=button):
                self.ui.on_reset()
                self.engine.reset_with_mines(5, 5, 3, {(1, 1), (3, 1), (3, 3)})
                self.install_recorder()
                with patch.object(self.ui._replay_recorder, "record_event", side_effect=ValueError("not appended")), \
                        patch("builtins.print"):
                    self.click((0, 0), button)
                counters = self.engine.get_counter_snapshot()
                self.assertEqual(counters["active_clicks"] + counters["wasted_clicks"], 1)
                self.assertEqual(self.ui._replay_recorder.events, ())
                self.assertFalse(self.recorder.eligible)
                self.assertIsNone(self.recorder.snapshot())
                self.assertFalse(self.ui.mouse_trace_record_checkbox.isEnabled())
                self.click((2, 0))
                self.assertEqual(len(self.ui._replay_recorder.events), 1)
                self.assertIsNone(self.recorder.snapshot())
                self.click((3, 3))
                self.assertEqual(self.engine.status, GameStatus.LOST)
                self.assertEqual(len(self.ui._replay_recorder.events), 2)
                self.assertIsNone(self.recorder.snapshot())
                self.assertFalse(self.ui.mouse_trace_display_checkbox.isEnabled())

    def test_started_trace_is_discarded_on_open_flag_or_chord_replay_append_failure(self):
        cases = ((Action.OPEN, (2, 0), Qt.LeftButton),
                 (Action.FLAG, (1, 1), Qt.RightButton),
                 (Action.CHORD, (0, 0), Qt.LeftButton))
        for action, target, button in cases:
            with self.subTest(action=action):
                self.ui.on_reset()
                self.engine.reset_with_mines(5, 5, 3, {(1, 1), (3, 1), (3, 3)})
                self.install_recorder()
                self.click()
                self.assertIsNotNone(self.recorder.snapshot())
                events = self.ui._replay_recorder.events
                with patch.object(self.ui._replay_recorder, "record_event", side_effect=ValueError("not appended")) as append, \
                        patch("builtins.print"):
                    self.click(target, button)
                self.assertEqual(append.call_args.kwargs["action"], action)
                counters = self.engine.get_counter_snapshot()
                self.assertEqual(counters["active_clicks"] + counters["wasted_clicks"], 2)
                self.assertEqual(self.ui._replay_recorder.events, events)
                self.assertFalse(self.recorder.eligible)
                self.assertIsNone(self.recorder.snapshot())
                self.assertFalse(self.ui.mouse_trace_record_checkbox.isEnabled())
                self.click((4, 0))
                self.assertIsNone(self.recorder.snapshot())
                self.click((3, 3))
                self.assertEqual(self.engine.status, GameStatus.LOST)
                self.assertFalse(self.ui.mouse_trace_display_checkbox.isEnabled())
                self.assertIsNone(self.ui.mouse_trace_overlay._trace)

    def test_terminal_replay_append_failure_never_exposes_finished_path(self):
        for started in (False, True):
            for won in (False, True):
                with self.subTest(started=started, won=won):
                    width = 4 if started else 2
                    self.ui._rebuild_game(width, 1, 1)
                    self.engine.reset_with_mines(width, 1, 1, {(width - 1, 0)})
                    self.install_recorder()
                    self.app.processEvents()
                    if started:
                        self.click((2, 0))
                        self.assertEqual(self.engine.status, GameStatus.PLAYING)
                        self.assertIsNotNone(self.recorder.snapshot())
                    with patch.object(self.ui._replay_recorder, "record_event", side_effect=ValueError("not appended")), \
                            patch("builtins.print"):
                        self.click((0, 0) if won else (width - 1, 0))
                    self.assertEqual(self.engine.status, GameStatus.WON if won else GameStatus.LOST)
                    self.assertFalse(self.recorder.eligible)
                    self.assertTrue(self.recorder.frozen)
                    self.assertIsNone(self.recorder.snapshot())
                    self.assertFalse(self.ui.mouse_trace_display_checkbox.isEnabled())
                    self.ui.mouse_trace_display_checkbox.setChecked(True)
                    self.assertFalse(self.ui.mouse_trace_display_checkbox.isChecked())
                    self.assertFalse(self.ui.mouse_trace_overlay.isVisible())
                    self.assertIsNone(self.ui.mouse_trace_overlay._trace)

    def test_noncommitted_action_with_missing_replay_preserves_recording_policy(self):
        for started, enabled in ((False, True), (False, False), (True, True)):
            with self.subTest(started=started, enabled=enabled):
                self.ui.on_reset()
                self.engine.reset_with_mines(5, 5, 3, {(1, 1), (3, 1), (3, 3)})
                self.install_recorder()
                self.ui.mouse_trace_record_checkbox.setChecked(enabled)
                if started:
                    self.click()

                def policy():
                    return (self.recorder.eligible, self.recorder.started, self.recorder.frozen,
                            self.ui.mouse_trace_record_checkbox.isChecked(),
                            self.ui.mouse_trace_record_checkbox.isEnabled(),
                            self.ui._mouse_trace_recording_locked, self.markers())

                before = policy()
                counters = self.engine.get_counter_snapshot()
                events = self.ui._replay_recorder.events
                with patch.object(self.engine, "step", return_value=(None, None, None, None, {})), \
                        patch.object(self.ui._replay_recorder, "record_event", side_effect=ValueError("not appended")), \
                        patch("builtins.print"):
                    self.click((2, 0))
                self.assertEqual(policy(), before)
                self.assertEqual(self.engine.get_counter_snapshot(), counters)
                self.assertEqual(self.ui._replay_recorder.events, events)
                if not started:
                    self.assertIsNone(self.recorder.snapshot())
                    self.ui.mouse_trace_record_checkbox.setChecked(True)
                self.click((2, 0))
                self.assertTrue(self.recorder.eligible)
                self.assertEqual(len(self.markers()), len(events) + 1)

    def test_pre_start_untimed_chord_append_failure_preserves_future_trace(self):
        self.ui.on_chord_mode_changed(ChordMode.BOTH_CLICK)
        self.ui.mouse_trace_record_checkbox.setChecked(False)
        self.press((0, 0))
        self.press((0, 0), Qt.RightButton)
        with patch.object(self.ui._replay_recorder, "record_event", side_effect=ValueError("not appended")) as append, \
                patch("builtins.print"):
            self.release((0, 0), Qt.RightButton)
            self.release((0, 0))
        append.assert_called_once()
        self.assertEqual(append.call_args.kwargs["action"], Action.CHORD)
        self.assertTrue(self.recorder.eligible)
        self.assertIsNone(self.recorder.snapshot())
        self.assertTrue(self.ui.mouse_trace_record_checkbox.isEnabled())
        self.assertFalse(self.ui._mouse_trace_recording_locked)
        self.ui.mouse_trace_record_checkbox.click()
        self.clock.return_value += 1_000_000
        self.click()
        self.assertEqual((self.markers()[0].elapsed_us, self.markers()[0].replay_event_index), (0, 0))
        self.assertFalse(self.ui.mouse_trace_record_checkbox.isEnabled())

    def test_board_capture_failure_after_successful_event_append_keeps_trace_eligible(self):
        with patch.object(self.ui, "_capture_replay_board_if_ready", side_effect=ValueError("board capture failed")), \
                patch("builtins.print"):
            self.click()
        self.assertEqual(len(self.ui._replay_recorder.events), 1)
        self.assertTrue(self.recorder.eligible)
        self.assertEqual(self.markers()[0].replay_event_index, 0)
        self.click((2, 0))
        self.assertEqual([p.replay_event_index for p in self.markers()], [0, 1])

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

    def finish_small_game(self, *, won=True, recording=True):
        self.ui._rebuild_game(2, 1, 1)
        self.engine.reset_with_mines(2, 1, 1, {(1, 0)})
        self.install_recorder()
        self.ui.mouse_trace_record_checkbox.setChecked(recording)
        self.app.processEvents()
        self.click((0, 0) if won else (1, 0))

    def paint_overlay(self):
        with patch("mouse_trace_ui.QPainter") as painter_class:
            self.ui.mouse_trace_overlay._draw_geometry(painter_class.return_value)
        return painter_class.return_value

    def test_recording_default_and_pre_action_choice_are_session_local(self):
        record = self.ui.mouse_trace_record_checkbox
        display = self.ui.mouse_trace_display_checkbox
        before = self.settings.allKeys()
        self.assertEqual(record.text(), "마우스 경로 기록")
        self.assertEqual(display.text(), "마우스 경로 표시")
        self.assertTrue(record.isChecked())
        self.assertTrue(record.isEnabled())
        record.click()
        self.assertFalse(record.isChecked())
        self.assertTrue(self.recorder.eligible)
        record.click()
        self.assertTrue(record.isChecked())
        self.assertIsNone(self.recorder.snapshot())
        self.assertEqual(self.settings.allKeys(), before)
        record.click()
        another = MinesweeperUI(MinesweeperEngine(2, 1, 1))
        try:
            self.assertTrue(another.mouse_trace_record_checkbox.isChecked())
        finally:
            another.close()
            another.deleteLater()

    def test_untimed_chord_keeps_recording_choice_editable(self):
        self.ui.on_chord_mode_changed(ChordMode.BOTH_CLICK)
        self.ui.mouse_trace_record_checkbox.setChecked(False)
        self.press((0, 0))
        self.press((0, 0), Qt.RightButton)
        self.release((0, 0), Qt.RightButton)
        self.release((0, 0))
        self.assertEqual(self.ui._replay_recorder.events[0].action, "CHORD")
        self.assertTrue(self.ui.mouse_trace_record_checkbox.isEnabled())
        self.assertTrue(self.recorder.eligible)
        self.ui.mouse_trace_record_checkbox.click()
        self.click()
        self.assertFalse(self.ui.mouse_trace_record_checkbox.isEnabled())
        self.assertEqual(self.markers()[0].replay_event_index, 1)

    def test_first_physical_open_or_flag_locks_choice_with_on_or_off_policy(self):
        for enabled in (True, False):
            for button in (Qt.LeftButton, Qt.RightButton):
                with self.subTest(enabled=enabled, button=button):
                    self.ui.on_reset()
                    self.engine.reset_with_mines(5, 5, 3, {(1, 1), (3, 1), (3, 3)})
                    self.install_recorder()
                    record = self.ui.mouse_trace_record_checkbox
                    record.setChecked(enabled)
                    self.click((0, 0), button)
                    self.assertFalse(record.isEnabled())
                    self.assertEqual(self.recorder.eligible, enabled)
                    self.assertEqual(self.recorder.started, enabled)
                    record.click()  # Disabled mouse/keyboard activation is inert.
                    self.assertEqual(record.isChecked(), enabled)
                    record.setChecked(not enabled)  # A late programmatic toggle cannot change policy.
                    self.assertEqual(record.isChecked(), enabled)
                    self.click((2, 0))
                    if enabled:
                        self.assertEqual([p.replay_event_index for p in self.markers()], [0, 1])
                    else:
                        self.assertIsNone(self.recorder.snapshot())

    def test_recording_lock_depends_on_gameplay_commit_not_replay_append(self):
        with patch.object(self.engine, "step", return_value=(None, None, None, None, {})):
            self.click()
        self.assertTrue(self.ui.mouse_trace_record_checkbox.isEnabled())
        with patch.object(self.ui._replay_recorder, "record_event", side_effect=ValueError("failed")), \
                patch("builtins.print"):
            self.click()
        self.assertFalse(self.ui.mouse_trace_record_checkbox.isEnabled())
        self.assertIsNone(self.recorder.snapshot())

    def test_fresh_game_transitions_preserve_recording_choice_and_unlock(self):
        transitions = (
            self.ui.on_reset,
            lambda: self.ui._rebuild_game(7, 4, 3),
            lambda: self.ui.on_difficulty_changed("초급 (9x9, 10)"),
            lambda: self.ui.on_difficulty_changed("커스텀"),
        )
        for enabled in (True, False):
            for transition in transitions:
                with self.subTest(enabled=enabled, transition=transition):
                    self.ui.on_reset()
                    self.ui.mouse_trace_record_checkbox.setChecked(enabled)
                    self.click((0, 0), Qt.RightButton)
                    self.assertFalse(self.ui.mouse_trace_record_checkbox.isEnabled())
                    with patch.object(self.ui, "_ask_custom_dimensions", return_value=(8, 6, 4)):
                        transition()
                    self.app.processEvents()
                    self.assertTrue(self.ui.mouse_trace_record_checkbox.isEnabled())
                    self.assertEqual(self.ui.mouse_trace_record_checkbox.isChecked(), enabled)
                    self.assertIsNone(self.ui._mouse_trace_recorder.snapshot())
                    self.assertTrue(self.ui._mouse_trace_recorder.eligible)

    def test_auto_before_any_human_action_locks_only_when_executed(self):
        self.ui.on_reset()
        self.install_recorder()
        self.ui.mouse_trace_record_checkbox.setChecked(False)
        self.ui.simple_auto_checkbox.setChecked(True)
        self.assertTrue(self.ui._simple_auto_pending)
        self.assertTrue(self.ui.mouse_trace_record_checkbox.isEnabled())
        self.assertTrue(self.recorder.eligible)
        self.ui._simple_auto_timer.timeout.emit()
        self.assertEqual(len(self.ui._replay_recorder.events), 1)
        self.assertFalse(self.ui.mouse_trace_record_checkbox.isEnabled())
        self.assertFalse(self.recorder.eligible)

    def test_display_is_unavailable_throughout_playing(self):
        display = self.ui.mouse_trace_display_checkbox
        for started in (False, True):
            with self.subTest(started=started):
                if started:
                    self.click()
                self.assertFalse(display.isEnabled())
                self.assertFalse(display.isChecked())
                display.setChecked(True)
                self.assertFalse(display.isChecked())
                self.assertFalse(self.ui.mouse_trace_overlay.isVisible())
                self.assertIsNone(self.ui.mouse_trace_overlay._trace)

    def test_won_and_lost_trace_available_off_until_explicitly_shown(self):
        for won in (True, False):
            with self.subTest(won=won):
                self.finish_small_game(won=won)
                display = self.ui.mouse_trace_display_checkbox
                overlay = self.ui.mouse_trace_overlay
                self.assertEqual(self.engine.status, GameStatus.WON if won else GameStatus.LOST)
                self.assertTrue(self.recorder.frozen)
                self.assertTrue(display.isEnabled())
                self.assertFalse(display.isChecked())
                self.assertFalse(overlay.isVisible())
                self.assertEqual(overlay._trace, self.recorder.snapshot())
                display.click()
                self.assertTrue(overlay.isVisible())
                self.assertEqual(self.paint_overlay().drawEllipse.call_count, 1)
                display.click()
                self.assertFalse(overlay.isVisible())

    def test_terminal_without_trace_cannot_enable_display(self):
        for cause in ("disabled", "auto", "no observed release"):
            with self.subTest(cause=cause):
                self.ui._rebuild_game(2, 1, 1)
                self.engine.reset_with_mines(2, 1, 1, {(1, 0)})
                self.install_recorder()
                self.app.processEvents()
                if cause == "disabled":
                    self.ui.mouse_trace_record_checkbox.setChecked(False)
                    self.click()
                elif cause == "auto":
                    self.ui.simple_auto_checkbox.setChecked(True)
                    self.ui.allow_guess_checkbox.setChecked(True)
                    self.assertTrue(self.ui._simple_auto_pending)
                    self.ui._simple_auto_timer.timeout.emit()
                else:
                    self.ui.on_left_click(0, 0)
                self.assertIn(self.engine.status, (GameStatus.WON, GameStatus.LOST))
                self.assertIsNone(self.recorder.snapshot())
                self.assertFalse(self.ui.mouse_trace_display_checkbox.isEnabled())
                self.ui.mouse_trace_display_checkbox.setChecked(True)
                self.assertFalse(self.ui.mouse_trace_display_checkbox.isChecked())
                self.assertFalse(self.ui.mouse_trace_overlay.isVisible())

    def test_new_game_hides_and_clears_finished_overlay(self):
        for transition in (self.ui.on_reset, lambda: self.ui._rebuild_game(5, 5, 3)):
            with self.subTest(transition=transition):
                self.finish_small_game()
                self.ui.mouse_trace_display_checkbox.click()
                transition()
                self.assertFalse(self.ui.mouse_trace_overlay.isVisible())
                self.assertIsNone(self.ui.mouse_trace_overlay._trace)
                self.assertIsNone(self.ui._mouse_trace_display_data)
                self.assertFalse(self.ui.mouse_trace_display_checkbox.isChecked())
                self.assertFalse(self.ui.mouse_trace_display_checkbox.isEnabled())

    def test_display_toggle_changes_only_presentation(self):
        self.finish_small_game()
        self.ui._analysis_result = object()
        cell = self.ui._buttons[(0, 0)]
        cell.setToolTip("unchanged tooltip")

        def state():
            return (self.engine.get_board_snapshot(), self.engine.get_observation(),
                    self.engine.get_counter_snapshot(), self.engine.get_stats(),
                    self.ui._replay_recorder.events, self.recorder.snapshot(),
                    self.ui._analysis_result, self.ui._analysis_observation,
                    cell.toolTip(), cell.analysis_overlay, cell.isDown(), self.ui._mouse_preview.copy())

        before = state()
        with patch.object(self.engine, "step", wraps=self.engine.step) as step, \
                patch.object(self.ui, "_clear_live_analysis", wraps=self.ui._clear_live_analysis) as clear:
            self.ui.mouse_trace_display_checkbox.click()
            self.ui.mouse_trace_display_checkbox.click()
        step.assert_not_called()
        clear.assert_not_called()
        self.assertEqual(state(), before)

    def test_visible_overlay_preserves_board_target_and_physical_event_delivery(self):
        self.finish_small_game()
        self.ui.mouse_trace_display_checkbox.click()
        overlay = self.ui.mouse_trace_overlay
        self.assertTrue(overlay.testAttribute(Qt.WA_TransparentForMouseEvents))
        before = self.ui._replay_recorder.events
        target = self.ui._buttons[(1, 0)]
        global_pos = self.point((1, 0))
        self.assertIs(self.ui.board_container.childAt(self.ui.board_container.mapFromGlobal(global_pos)), target)
        self.assertIs(self.ui._cell_at_mouse_position(global_pos), target)
        delivered = QSignalSpy(target.mouse_input)
        QTest.mouseClick(self.ui.windowHandle(), Qt.LeftButton, pos=self.ui.mapFromGlobal(global_pos))
        self.assertGreaterEqual(len(delivered), 2)
        self.assertEqual(self.ui._replay_recorder.events, before)  # Terminal routing remains inert.

    def test_recorded_exit_gap_stays_separate_in_finished_overlay(self):
        self.click()
        self.hover((1, 0))
        self.hover(self.outside())
        self.hover((2, 0))
        self.click((3, 3))
        self.assertEqual(self.engine.status, GameStatus.LOST)
        data = self.recorder.snapshot()
        self.assertEqual(len(data.segments), 2)
        self.ui.mouse_trace_display_checkbox.click()
        painter = self.paint_overlay()
        polygons = [[(p.x(), p.y()) for p in call.args[0]]
                    for call in painter.drawPolyline.call_args_list]
        self.assertEqual(polygons, [[(p.x, p.y) for p in s.points] for s in data.segments])

    def test_mixed_live_sizes_and_terminal_resize_preserve_trace_geometry(self):
        self.click()
        self.ui.on_cell_size_changed(56)
        self.app.processEvents()
        self.click((3, 3))
        data = self.recorder.snapshot()
        self.assertEqual([s.cell_size for s in data.segments], [28, 56])
        self.ui.mouse_trace_display_checkbox.click()
        self.ui.on_cell_size_changed(14)
        self.app.processEvents()
        overlay = self.ui.mouse_trace_overlay
        self.assertEqual((overlay.width(), overlay.height()), (70, 70))
        self.assertTrue(overlay.isVisible())
        self.assertEqual(self.recorder.snapshot(), data)
        painter = self.paint_overlay()
        positions = [(call.args[0].x(), call.args[0].y()) for call in painter.drawEllipse.call_args_list]
        self.assertEqual(positions, [(p.x * 14 / s.cell_size, p.y * 14 / s.cell_size)
                                     for s in data.segments for p in s.points if p.replay_event_index is not None])

    def test_large_board_overlay_scrolls_and_clips_with_existing_viewport(self):
        self.ui._rebuild_game(50, 50, 10)
        self.engine.reset_with_mines(50, 50, 10, {(x, 1) for x in range(10)})
        self.install_recorder()
        self.ui.resize(1000, 650)
        self.app.processEvents()
        self.click()
        self.click((0, 1))
        self.ui.mouse_trace_display_checkbox.click()
        overlay = self.ui.mouse_trace_overlay
        before = self.recorder.snapshot()
        self.ui.scroll_area.horizontalScrollBar().setValue(280)
        self.ui.scroll_area.verticalScrollBar().setValue(280)
        self.app.processEvents()
        self.assertIs(overlay.parentWidget(), self.ui.board_container)
        self.assertEqual(overlay.geometry(), self.ui.board_container.rect())
        self.assertFalse(overlay.visibleRegion().contains(QPoint(0, 0)))
        self.assertTrue(overlay.visibleRegion().contains(QPoint(300, 300)))
        self.assertEqual(self.recorder.snapshot(), before)
        self.assertIs(self.ui._cell_at_mouse_position(self.point((12, 11))), self.ui._buttons[(12, 11)])

    def test_trace_free_current_replay_and_save_load_remain_v1(self):
        self.finish_small_game(recording=False)
        data = self.ui._replay_recorder.to_replay_data()
        self.ui.on_view_current_replay()
        self.assertTrue(self.ui._replay_mode)
        self.assertEqual(self.ui._replay_data, data)
        self.assertFalse(self.ui.mouse_trace_record_checkbox.isEnabled())
        self.assertFalse(self.ui.mouse_trace_display_checkbox.isEnabled())
        self.assertFalse(self.ui.mouse_trace_display_checkbox.isChecked())
        self.assertIsNone(self.ui.mouse_trace_overlay._trace)
        self.ui.on_replay_last()
        self.ui.mouse_trace_display_checkbox.setChecked(True)
        self.assertFalse(self.ui.mouse_trace_overlay.isVisible())
        root = Path(self.settings.fileName()).parent
        named = root / "named.json"
        with patch.object(self.ui, "_select_auto_replay_directory", return_value=str(root)), \
                patch("ui_manager.QFileDialog.getSaveFileName", return_value=(str(named), "")), \
                patch("ui_manager.QMessageBox.information"):
            self.ui.on_save_replay()
            self.ui.on_save_replay_as()
        files = list(root.glob("*.json"))
        self.assertEqual(len(files), 2)
        for path in files:
            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(document["schema_version"], 1)
            self.assertNotIn("mouse_trace", document)
            self.assertEqual(load_replay_json(str(path)), data)
        self.ui.on_exit_replay()
        self.assertTrue(self.ui.mouse_trace_record_checkbox.isEnabled())
        with patch("ui_manager.QFileDialog.getOpenFileName", return_value=(str(named), "")):
            self.ui.on_load_replay()
        self.assertTrue(self.ui._replay_mode)
        self.assertEqual(self.ui._replay_data, data)
        self.assertFalse(self.ui.mouse_trace_display_checkbox.isEnabled())
        self.assertFalse(self.ui.mouse_trace_overlay.isVisible())

    def trace_replay(self):
        """An incomplete game with a pre-start CHORD and mixed-size trace prefix."""
        return ReplayData(
            ReplayBoard(5, 5, 3, {(1, 1), (3, 1), (3, 3)}),
            (ReplayEvent(0, 0, 0, "CHORD"), ReplayEvent(1, 0, 0, "OPEN"),
             ReplayEvent(2, 1, 1, "FLAG"), ReplayEvent(3, 0, 0, "CHORD")),
            "human", 2, MouseTraceData(5, 5, (
                MouseTraceSegment(28, (MouseTracePoint(0, 4.25, 7, 1),
                                       MouseTracePoint(100, 32, 14.5))),
                MouseTraceSegment(56, (MouseTracePoint(200, 80.5, 81, 2),
                                       MouseTracePoint(300, 9, 14, 3))),
            )))

    def load_replay_file(self, path):
        with patch("ui_manager.QFileDialog.getOpenFileName", return_value=(str(path), "")):
            self.ui.on_load_replay()

    def test_finished_current_replay_carries_trace_and_resets_display_default(self):
        self.finish_small_game()
        trace = self.recorder.snapshot()
        events = self.ui._replay_recorder.events
        self.ui.mouse_trace_display_checkbox.click()
        self.ui.on_view_current_replay()
        replay = self.ui._replay_data
        self.assertEqual(replay.schema_version, 2)
        self.assertEqual(replay.mouse_trace, trace)
        self.assertEqual(replay.events, events)
        self.assertIs(self.ui._replay_player.replay_data, replay)
        self.assertIs(self.ui.mouse_trace_overlay._trace, replay.mouse_trace)
        self.assertEqual(self.ui.mouse_trace_overlay._events, events)
        self.assertIsNone(self.recorder.snapshot())  # No Live side channel survives entry.
        self.assertFalse(self.ui.mouse_trace_record_checkbox.isEnabled())
        self.assertTrue(self.ui.mouse_trace_display_checkbox.isEnabled())
        self.assertFalse(self.ui.mouse_trace_display_checkbox.isChecked())
        self.assertFalse(self.ui.mouse_trace_overlay.isVisible())
        self.ui.mouse_trace_display_checkbox.click()
        self.assertTrue(self.ui.mouse_trace_overlay.isVisible())
        root = Path(self.settings.fileName()).parent
        named = root / "current.json"
        self.ui.on_replay_last()
        with patch("ui_manager.QFileDialog.getSaveFileName", return_value=(str(named), "")), \
                patch("ui_manager.QMessageBox.information"):
            self.ui.on_save_replay_as()
        self.assertEqual(load_replay_json(named), replay)

    def test_in_progress_live_save_and_save_as_snapshot_prefix_without_freezing(self):
        self.click()
        self.hover((2, 0))
        trace = self.recorder.snapshot()
        self.assertEqual(self.engine.status, GameStatus.PLAYING)
        root = Path(self.settings.fileName()).parent
        named = root / "prefix.json"
        with patch.object(self.ui, "_select_auto_replay_directory", return_value=str(root)), \
                patch("ui_manager.QFileDialog.getSaveFileName", return_value=(str(named), "")), \
                patch("ui_manager.QMessageBox.information"):
            self.ui.on_save_replay()
            self.ui.on_save_replay_as()
        files = {path: path.read_bytes() for path in root.glob("*.json")}
        self.assertEqual(len(files), 2)
        saved = load_replay_json(named)
        self.assertEqual(saved.schema_version, 2)
        self.assertEqual(saved.mouse_trace, trace)
        self.assertFalse(self.recorder.frozen)
        self.assertTrue(self.recorder.eligible)
        self.assertFalse(self.ui.mouse_trace_display_checkbox.isEnabled())
        self.clock.return_value += 1_000_000
        self.hover((4, 0))
        self.click((1, 1), Qt.RightButton)
        self.assertGreater(len(self.points()), sum(len(s.points) for s in trace.segments))
        self.assertEqual(len(self.ui._replay_recorder.events), len(saved.events) + 1)
        self.assertEqual(saved.mouse_trace, trace)
        for path, content in files.items():
            self.assertEqual(path.read_bytes(), content)
            self.assertEqual(load_replay_json(path), saved)

    def test_disabled_or_auto_invalidated_live_saves_stay_v1(self):
        root = Path(self.settings.fileName()).parent
        for invalidated in (False, True):
            with self.subTest(invalidated=invalidated):
                self.ui.on_reset()
                self.engine.reset_with_mines(5, 5, 3, {(1, 1), (3, 1), (3, 3)})
                self.install_recorder()
                self.ui.mouse_trace_record_checkbox.setChecked(invalidated)
                self.click()
                if invalidated:
                    self.ui.simple_auto_checkbox.setChecked(True)
                    self.ui.allow_guess_checkbox.setChecked(True)
                    self.ui._simple_auto_timer.timeout.emit()
                    self.ui.simple_auto_checkbox.setChecked(False)
                self.assertFalse(self.recorder.eligible)
                path = root / f"trace-free-{invalidated}.json"
                with patch("ui_manager.QFileDialog.getSaveFileName", return_value=(str(path), "")), \
                        patch("ui_manager.QMessageBox.information"):
                    self.ui.on_save_replay_as()
                self.assertEqual(load_replay_json(path).schema_version, 1)
                self.assertNotIn("mouse_trace", json.loads(path.read_text(encoding="utf-8")))

    def test_inconsistent_live_attachment_fails_instead_of_saving_v1(self):
        self.click()
        invalid = replace(self.recorder.snapshot(), width=6)
        with patch.object(self.recorder, "snapshot", return_value=invalid), \
                patch("ui_manager.QMessageBox.information") as message, \
                patch("ui_manager.save_replay_json") as save:
            self.ui.on_save_replay()
        save.assert_not_called()
        message.assert_called_once()
        self.assertFalse(self.ui._replay_mode)
        self.assertTrue(self.recorder.eligible)
        self.assertFalse(self.recorder.frozen)

    def test_loaded_incomplete_v2_exposes_static_prefix_and_preserves_statistics(self):
        replay = self.trace_replay()
        path = Path(self.settings.fileName()).parent / "incomplete.json"
        save_replay_json(replay, path)
        self.load_replay_file(path)
        self.assertEqual(self.ui._replay_data, replay)
        self.assertFalse(self.ui.mouse_trace_record_checkbox.isEnabled())
        self.assertTrue(self.ui.mouse_trace_display_checkbox.isEnabled())
        self.assertFalse(self.ui.mouse_trace_display_checkbox.isChecked())
        self.ui.mouse_trace_display_checkbox.click()
        self.assertTrue(self.ui.mouse_trace_overlay.isVisible())
        self.ui.on_replay_last()
        self.assertEqual(self.ui._replay_player.engine.status, GameStatus.PLAYING)
        timeline = ReplayStatisticsAnalyzer.analyze(replay)
        self.assertFalse(timeline.is_completed)
        self.assertEqual(timeline, ReplayStatisticsAnalyzer.analyze(
            replace(replay, schema_version=1, mouse_trace=None)))
        self.assertEqual(self.ui.mouse_trace_overlay._trace, replay.mouse_trace)

    def test_replay_path_is_static_across_seek_autoplay_and_speed_controls(self):
        replay = self.trace_replay()
        for shown in (False, True):
            with self.subTest(shown=shown):
                self.ui._enter_replay_mode(ReplayPlayer(replay))
                self.ui.mouse_trace_display_checkbox.setChecked(shown)

                def assert_static():
                    self.assertIs(self.ui._replay_data, replay)
                    self.assertIs(self.ui.mouse_trace_overlay._trace, replay.mouse_trace)
                    self.assertEqual(self.ui.mouse_trace_overlay._events, replay.events)
                    self.assertEqual(self.ui.mouse_trace_display_checkbox.isChecked(), shown)
                    self.assertEqual(self.ui.mouse_trace_overlay.isVisible(), shown)

                self.ui.replay_playback_mode_combo.setCurrentText(REPLAY_MODE_INDEX)
                for move in (self.ui.on_replay_next, self.ui.on_replay_last,
                             self.ui.on_replay_previous, self.ui.on_replay_first,
                             lambda: self.ui.replay_slider.setValue(2)):
                    move()
                    assert_static()
                self.ui.on_replay_first()
                self.ui.on_replay_play_pause()
                self.ui.replay_index_interval_spin.setValue(500)
                self.ui._advance_replay_autoplay()
                self.assertEqual(self.ui._replay_player.current_index, 1)
                assert_static()
                self.ui._stop_replay_autoplay()
                self.ui.replay_playback_mode_combo.setCurrentText(REPLAY_MODE_TIME)
                self.ui.replay_slider.setValue(2000)
                assert_static()
                self.ui.on_replay_first()
                self.ui.replay_time_speed_spin.setValue(1.0)
                with patch("ui_manager.time.perf_counter", return_value=100.0) as clock:
                    self.ui.on_replay_play_pause()
                    clock.return_value = 101.5
                    self.ui._advance_replay_autoplay()
                    self.assertEqual(self.ui._replay_player.current_index, 2)
                    assert_static()
                    self.ui.replay_time_speed_spin.setValue(2.0)
                    assert_static()
                    clock.return_value = 103.5
                    self.ui._advance_replay_autoplay()
                    self.assertEqual(self.ui._replay_player.current_index, len(replay.events))
                    assert_static()

    def test_replay_overlay_rescales_full_segments_without_seek_dependent_geometry(self):
        replay = self.trace_replay()
        self.ui._enter_replay_mode(ReplayPlayer(replay))
        self.ui.mouse_trace_display_checkbox.click()
        self.ui.on_cell_size_changed(14)
        for move in (self.ui.on_replay_first, self.ui.on_replay_last):
            move()
            painter = self.paint_overlay()
            polygons = [[(p.x(), p.y()) for p in call.args[0]]
                        for call in painter.drawPolyline.call_args_list]
            self.assertEqual(polygons, [[(p.x * 14 / s.cell_size, p.y * 14 / s.cell_size)
                                         for p in s.points] for s in replay.mouse_trace.segments])
            markers = [(call.args[0].x(), call.args[0].y()) for call in painter.drawEllipse.call_args_list]
            self.assertEqual(markers, [(p.x * 14 / s.cell_size, p.y * 14 / s.cell_size)
                                       for s in replay.mouse_trace.segments for p in s.points
                                       if p.replay_event_index is not None])
            self.assertTrue(self.ui.mouse_trace_overlay.isVisible())

    def test_loaded_replay_save_and_save_as_keep_whole_attachment_at_index_two(self):
        replay = self.trace_replay()
        root = Path(self.settings.fileName()).parent
        original = root / "original.json"
        save_replay_json(replay, original)
        self.load_replay_file(original)
        self.ui.on_replay_next()
        self.ui.on_replay_next()
        self.assertEqual(self.ui._replay_player.current_index, 2)
        named = root / "copy.json"
        with patch.object(self.ui, "_select_auto_replay_directory", return_value=str(root)), \
                patch("ui_manager.QFileDialog.getSaveFileName", return_value=(str(named), "")), \
                patch("ui_manager.QMessageBox.information"):
            self.ui.on_save_replay()
            self.ui.on_save_replay_as()
        files = list(root.glob("*.json"))
        self.assertEqual(len(files), 3)
        for path in files:
            self.assertEqual(load_replay_json(path), replay)
        self.assertEqual(self.ui._replay_player.current_index, 2)

    def test_malformed_v2_load_preserves_live_and_existing_replay_sessions(self):
        self.click()
        path = Path(self.settings.fileName()).parent / "malformed.json"
        invalid = replay_data_to_dict(self.trace_replay())
        invalid["mouse_trace"]["segments"][1]["points"][0]["replay_event_index"] = 99
        path.write_text(json.dumps(invalid), encoding="utf-8")
        for mode in ("live", "replay"):
            with self.subTest(mode=mode):
                if mode == "replay":
                    self.ui._enter_replay_mode(ReplayPlayer(self.trace_replay()))
                    self.ui.on_replay_next()
                    self.ui.mouse_trace_display_checkbox.click()

                def state():
                    player = self.ui._replay_player
                    return (self.engine.get_board_snapshot(), self.engine.get_counter_snapshot(),
                            self.engine.get_observation(), self.ui._replay_recorder.events,
                            self.recorder.snapshot(), self.recorder.eligible, self.recorder.frozen,
                            self.ui._replay_mode, self.ui._replay_data, player,
                            player.current_index if player else None,
                            self.ui.mouse_trace_overlay._trace, self.ui.mouse_trace_overlay.isVisible(),
                            self.ui.mouse_trace_display_checkbox.isEnabled(),
                            self.ui.mouse_trace_display_checkbox.isChecked(),
                            self.ui.mouse_trace_record_checkbox.isEnabled())

                before = state()
                with patch("ui_manager.QMessageBox.warning") as warning, \
                        patch.object(self.ui, "_enter_replay_mode") as enter:
                    self.load_replay_file(path)
                enter.assert_not_called()
                warning.assert_called_once()
                self.assertEqual(warning.call_args.args[1], "리플레이 불러오기 실패")
                self.assertEqual(state(), before)

    def test_exit_v2_replay_clears_presentation_and_preserves_recording_preference(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                self.ui.mouse_trace_record_checkbox.setChecked(enabled)
                self.ui._enter_replay_mode(ReplayPlayer(self.trace_replay()))
                self.ui.mouse_trace_display_checkbox.click()
                self.ui.on_exit_replay()
                self.assertIsNone(self.ui._replay_data)
                self.assertIsNone(self.ui.mouse_trace_overlay._trace)
                self.assertFalse(self.ui.mouse_trace_overlay.isVisible())
                self.assertFalse(self.ui.mouse_trace_display_checkbox.isEnabled())
                self.assertFalse(self.ui.mouse_trace_display_checkbox.isChecked())
                self.assertEqual(self.ui.mouse_trace_record_checkbox.isChecked(), enabled)
                self.assertTrue(self.ui.mouse_trace_record_checkbox.isEnabled())
                self.assertTrue(self.ui._mouse_trace_recorder.eligible)
                self.assertFalse(self.ui._mouse_trace_recorder.started)
                self.assertFalse(self.ui._mouse_trace_recorder.frozen)


if __name__ == "__main__":
    unittest.main()
