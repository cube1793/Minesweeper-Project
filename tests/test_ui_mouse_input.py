"""Real Qt release gestures, grab routing, preview purity and session invalidation."""

from copy import deepcopy
import os
import unittest
from unittest.mock import call, patch

from core_engine import Action, CellState, GameStatus, MinesweeperEngine
from replay_model import ReplayBoard, ReplayData
from replay_player import ReplayPlayer

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PyQt5.QtCore import QEvent, QPoint, QPointF, Qt
    from PyQt5.QtGui import QMouseEvent
    from PyQt5.QtTest import QTest
    from PyQt5.QtWidgets import QApplication
except ImportError:
    QApplication = None
else:
    from ui_manager import ChordMode, MinesweeperUI


@unittest.skipIf(QApplication is None, "PyQt5 unavailable")
class MouseInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        # Worker execution is unrelated to pointer dispatch. Engine, recorder,
        # timers, rendering, and all mouse handlers remain real.
        worker = patch.object(MinesweeperUI, "_ensure_zini_metric_job")
        self.worker = worker.start()
        self.addCleanup(worker.stop)
        self.engine = MinesweeperEngine(5, 5, 3)
        self.engine.reset_with_mines(5, 5, 3, {(1, 1), (3, 1), (3, 3)})
        self.ui = MinesweeperUI(self.engine)
        self.addCleanup(self.close_ui)
        self.ui.show()
        self.ui.activateWindow()
        self.app.processEvents()
        step = patch.object(self.engine, "step", wraps=self.engine.step)
        self.step = step.start()
        self.addCleanup(step.stop)
        self.held = Qt.NoButton
        self.receiver = None
        self.signals = []
        for cell in self.ui._buttons.values():
            for name in ("left", "right", "both"):
                getattr(cell, name + "_clicked").connect(
                    lambda x, y, name=name: self.signals.append((name, x, y)))

    def close_ui(self):
        self.ui._stop_timer()
        self.ui._stop_replay_autoplay()
        self.ui.close()
        self.ui.deleteLater()
        self.app.processEvents()

    def point(self, target):
        if isinstance(target, QPoint):
            return target
        button = self.ui._buttons[target]
        return button.mapToGlobal(button.rect().center())

    def window_point(self, target):
        return self.ui.mapFromGlobal(self.point(target))

    def outside(self):
        return self.ui.scroll_area.viewport().mapToGlobal(QPoint(-8, -8))

    def send(self, kind, target, button=Qt.NoButton, receiver=None):
        if kind in (QEvent.MouseButtonPress, QEvent.MouseButtonDblClick):
            if not self.held:
                self.receiver = receiver or self.ui._buttons[target]
            self.held |= button
        elif kind == QEvent.MouseButtonRelease:
            self.held &= ~button
        receiver = receiver or self.receiver
        global_pos = self.point(target)
        # Deliberately deliver moves/releases to the press receiver, even when
        # the global position is over a different cell or outside the board.
        event = QMouseEvent(kind, QPointF(receiver.mapFromGlobal(global_pos)),
                            QPointF(global_pos), button,
                            Qt.MouseButtons(self.held), Qt.NoModifier)
        self.app.sendEvent(receiver, event)

    def press(self, target, button=Qt.LeftButton):
        self.send(QEvent.MouseButtonPress, target, button)

    def move(self, target):
        self.send(QEvent.MouseMove, target)

    def release(self, target, button=Qt.LeftButton, receiver=None):
        self.send(QEvent.MouseButtonRelease, target, button, receiver)

    def down(self):
        return {xy for xy, cell in self.ui._buttons.items() if cell.isDown()}

    def neighbors(self, target):
        x, y = target
        obs = self.engine.get_observation()
        return {(nx, ny) for ny in range(max(0, y - 1), min(5, y + 2))
                for nx in range(max(0, x - 1), min(5, x + 2))
                if obs[ny][nx] == CellState.HIDDEN}

    def snapshot(self):
        return deepcopy((
            self.engine.get_observation(), self.engine.get_board_snapshot(),
            self.engine.status, self.engine.get_counter_snapshot(),
            self.engine._active_clicks, self.engine._wasted_clicks,
            self.engine._timer_started, self.engine._start_time, self.engine._end_time,
            self.ui._timer_running, self.ui._timer.isActive(),
            self.ui._replay_recorder.events, self.ui._replay_recorder.board,
            self.ui._zini_job_token, self.ui._zini_process_token,
            self.ui._zini_payload_path, self.ui._zini_result_path,
            self.ui._zini_poll_timer.isActive(), vars(self.ui._zini_explorer),
            self.ui._analysis_result, self.ui._analysis_observation,
            self.ui._simple_auto_pending, self.ui._simple_auto_timer.isActive(),
        ))

    def prepare_numbers(self, flag=True):
        self.ui.on_left_click(0, 0)
        self.ui.on_left_click(2, 0)
        if flag:
            self.ui.on_right_click(1, 1)
        self.step.reset_mock()
        self.worker.reset_mock()
        self.signals.clear()

    def assert_pure(self, before):
        self.assertEqual(self.snapshot(), before)
        self.step.assert_not_called()
        self.worker.assert_not_called()
        self.assertEqual(self.signals, [])

    def assert_last_event(self, action, target):
        event = self.ui._replay_recorder.events[-1]
        self.assertEqual((event.action, event.x, event.y), (action, *target))

    def assert_click_totals(self, total, left, right, chord):
        self.assertEqual(
            {key: self.engine._active_clicks[key] + self.engine._wasted_clicks[key]
             for key in ("total", "left", "right", "chord")},
            dict(total=total, left=left, right=right, chord=chord),
        )

    def assert_mouse_cleared(self):
        self.assertEqual(self.ui._mouse_buttons, Qt.NoButton)
        self.assertEqual(self.ui._mouse_origins, {})
        self.assertEqual(self.ui._mouse_left_suppressed, set())
        self.assertFalse(self.ui._mouse_both)
        self.assertFalse(self.ui._mouse_consumed)
        self.assertIsNone(self.ui._mouse_position)
        self.assertEqual(self.down(), set())

    def flag_during_left_hold(self, target=(1, 1)):
        self.press((0, 0))
        self.move(target)
        self.press(target, Qt.RightButton)
        self.release(target, Qt.RightButton)

    def test_qtest_left_press_and_release_boundary(self):
        cell = self.ui._buttons[(0, 0)]
        before = self.snapshot()
        QTest.mousePress(cell, Qt.LeftButton)
        self.assertEqual(self.down(), {(0, 0)})
        self.assert_pure(before)
        self.assertFalse(self.ui._timer_running)
        self.assertFalse(self.engine._timer_started)
        QTest.mouseRelease(cell, Qt.LeftButton)
        self.step.assert_called_once_with(0, 0, Action.OPEN)
        self.assertEqual(len(self.ui._replay_recorder.events), 1)
        self.assert_last_event("OPEN", (0, 0))
        self.assertTrue(self.ui._timer_running)
        self.assertTrue(self.engine._timer_started)
        self.assertEqual(self.down(), set())

    def test_unplaced_board_is_not_placed_until_release(self):
        self.ui.on_reset()
        before = self.snapshot()
        self.press((0, 0))
        self.move((1, 0))
        self.assert_pure(before)
        self.assertFalse(self.engine.get_board_snapshot().mines_placed)
        self.release((1, 0))
        self.step.assert_called_once_with(1, 0, Action.OPEN)
        self.assertTrue(self.engine.get_board_snapshot().mines_placed)

    def test_right_drag_commits_only_at_release_target(self):
        before = self.snapshot()
        self.press((0, 0), Qt.RightButton)
        self.move((1, 1))
        self.assertEqual(self.down(), set())
        self.assert_pure(before)
        self.release((1, 1), Qt.RightButton)
        self.step.assert_called_once_with(1, 1, Action.FLAG)
        self.assertEqual(len(self.ui._replay_recorder.events), 1)
        self.assert_last_event("FLAG", (1, 1))
        self.assertEqual(self.engine.get_observation()[0][0], CellState.HIDDEN)
        self.assertEqual(self.engine.get_observation()[1][1], CellState.FLAGGED)
        self.assertTrue(self.ui._timer_running)
        self.assertTrue(self.engine._timer_started)

    def test_right_toggle_preserves_existing_policy(self):
        cell = self.ui._buttons[(1, 1)]
        QTest.mouseClick(cell, Qt.RightButton)
        before = self.snapshot()
        QTest.mousePress(cell, Qt.RightButton)
        self.assertEqual(self.snapshot(), before)
        QTest.mouseRelease(cell, Qt.RightButton)
        self.assertEqual(self.engine.get_observation()[1][1], CellState.HIDDEN)
        self.assertEqual(self.step.call_count, 2)
        self.assertEqual([e.action for e in self.ui._replay_recorder.events],
                         ["FLAG", "FLAG"])

    def test_hidden_drag_transfers_preview_and_opens_only_destination(self):
        before = self.snapshot()
        self.press((0, 0))
        self.move((1, 0))
        self.assertEqual(self.down(), {(1, 0)})
        self.assert_pure(before)
        self.release((1, 0))
        self.step.assert_called_once_with(1, 0, Action.OPEN)
        self.assertEqual(self.engine.get_observation()[0][0], CellState.HIDDEN)
        self.assertEqual(self.engine.get_observation()[0][1], 1)
        self.assertEqual(self.down(), set())

    def test_release_position_wins_even_without_a_move_event(self):
        self.press((0, 0))
        self.release((1, 0))
        self.step.assert_called_once_with(1, 0, Action.OPEN)
        self.assertEqual(self.down(), set())

    def test_qwindow_automatic_grab_routes_cross_cell_events_to_origin(self):
        events = []
        origin = self.ui._buttons[(0, 0)]
        origin.mouse_input.connect(lambda cell, e: events.append((cell, e.type())))
        window = self.ui.windowHandle()
        a = self.ui.mapFromGlobal(self.point((0, 0)))
        b = self.ui.mapFromGlobal(self.point((1, 0)))
        QTest.mousePress(window, Qt.LeftButton, pos=a)
        QTest.mouseMove(window, b)
        self.assertEqual(self.down(), {(1, 0)})
        self.step.assert_not_called()
        QTest.mouseRelease(window, Qt.LeftButton, pos=b)
        self.assertIn((origin, QEvent.MouseMove), events)
        self.assertIn((origin, QEvent.MouseButtonRelease), events)
        self.step.assert_called_once_with(1, 0, Action.OPEN)
        self.assertEqual(self.engine.get_observation()[0][0], CellState.HIDDEN)

    def test_hidden_to_number_and_number_to_number_preview_is_pure(self):
        self.prepare_numbers()
        self.ui.analysis_checkbox.setChecked(True)
        before = self.snapshot()
        overlays = {xy: cell.analysis_overlay for xy, cell in self.ui._buttons.items()}
        self.press((0, 1))
        self.assertEqual(self.down(), {(0, 1)})
        for target in ((0, 0), (2, 0)):
            self.move(target)
            self.assertEqual(self.down(), self.neighbors(target))
            self.assertNotIn(target, self.down())
            self.assertNotIn((1, 1), self.down())
            self.assert_pure(before)
        self.assertEqual(overlays, {xy: cell.analysis_overlay
                                    for xy, cell in self.ui._buttons.items()})

    def test_hidden_origin_can_release_as_chord_on_number(self):
        self.prepare_numbers()
        count = len(self.ui._replay_recorder.events)
        self.press((4, 0))
        self.move((0, 0))
        self.assertEqual(self.down(), self.neighbors((0, 0)))
        self.release((0, 0))
        self.step.assert_called_once_with(0, 0, Action.CHORD)
        self.assertEqual(len(self.ui._replay_recorder.events), count + 1)
        self.assert_last_event("CHORD", (0, 0))
        self.assertEqual(self.engine.get_observation()[0][4], CellState.HIDDEN)

    def test_number_origin_can_release_as_open_on_hidden(self):
        self.prepare_numbers()
        self.press((0, 0))
        self.move((4, 0))
        self.assertEqual(self.down(), {(4, 0)})
        self.release((4, 0))
        self.step.assert_called_once_with(4, 0, Action.OPEN)

    def test_flag_outside_and_reentry_transfer_preview_without_actions(self):
        self.prepare_numbers()
        before = self.snapshot()
        self.press((0, 0))
        self.move((1, 1))
        self.assertEqual(self.down(), set())
        self.move(self.outside())
        self.assertEqual(self.down(), set())
        self.move((4, 0))
        self.assertEqual(self.down(), {(4, 0)})
        self.assert_pure(before)
        self.release((4, 0))
        self.step.assert_called_once_with(4, 0, Action.OPEN)

    def test_single_release_outside_does_nothing(self):
        for button in (Qt.LeftButton, Qt.RightButton):
            with self.subTest(button=button):
                before = self.snapshot()
                self.press((0, 0), button)
                self.move(self.outside())
                self.assertEqual(self.down(), set())
                self.release(self.outside(), button)
                self.assert_pure(before)
                self.assertEqual(self.ui._mouse_buttons, Qt.NoButton)

    def test_flag_never_depresses_but_left_wasted_accounting_is_preserved(self):
        self.prepare_numbers()
        before = self.snapshot()
        wasted = self.engine._wasted_clicks["left"]
        count = len(self.ui._replay_recorder.events)
        self.press((1, 1))
        self.assertEqual(self.down(), set())
        self.assert_pure(before)
        self.release((1, 1))
        self.step.assert_called_once_with(1, 1, Action.OPEN)
        self.assertEqual(self.engine._wasted_clicks["left"], wasted + 1)
        self.assertEqual(self.engine.get_observation()[1][1], CellState.FLAGGED)
        self.assertEqual(len(self.ui._replay_recorder.events), count + 1)
        self.assert_last_event("OPEN", (1, 1))

    def test_left_chord_preview_and_successful_release(self):
        self.prepare_numbers()
        before = self.snapshot()
        neighbors = self.neighbors((0, 0))
        active = self.engine._active_clicks["chord"]
        count = len(self.ui._replay_recorder.events)
        self.press((0, 0))
        self.assertEqual(self.down(), neighbors)
        self.assertTrue(neighbors)
        self.assert_pure(before)
        self.release((0, 0))
        self.step.assert_called_once_with(0, 0, Action.CHORD)
        for x, y in neighbors:
            self.assertGreaterEqual(self.engine.get_observation()[y][x], 0)
        self.assertEqual(self.engine._active_clicks["chord"], active + 1)
        self.assertEqual(len(self.ui._replay_recorder.events), count + 1)
        self.assertEqual(self.down(), set())

    def test_failed_chord_still_previews_and_records_one_wasted_attempt(self):
        self.prepare_numbers(flag=False)
        before = self.engine.get_observation()
        wasted = self.engine._wasted_clicks["chord"]
        count = len(self.ui._replay_recorder.events)
        self.press((0, 0))
        self.assertEqual(self.down(), self.neighbors((0, 0)))
        self.assertTrue(self.down())
        self.step.assert_not_called()
        self.release((0, 0))
        self.step.assert_called_once_with(0, 0, Action.CHORD)
        self.assertEqual(self.engine.get_observation(), before)
        self.assertEqual(self.engine._wasted_clicks["chord"], wasted + 1)
        self.assertEqual(len(self.ui._replay_recorder.events), count + 1)
        self.assert_last_event("CHORD", (0, 0))
        self.assertEqual(self.down(), set())

    def test_both_mode_number_left_records_one_wasted_open(self):
        self.prepare_numbers()
        self.ui.on_chord_mode_changed(ChordMode.BOTH_CLICK)
        # Cover a click on the number and the accepted drag-to-number policy.
        for origin in ((0, 0), (4, 0)):
            with self.subTest(origin=origin):
                before = self.snapshot()
                board = self.engine.get_board_snapshot()
                obs = self.engine.get_observation()
                wasted = self.engine._wasted_clicks.copy()
                active = self.engine._active_clicks.copy()
                count = len(self.ui._replay_recorder.events)
                self.press(origin)
                self.assertEqual(self.down(),
                                 {(4, 0)} if origin == (4, 0) else set())
                self.move((0, 0))
                self.assertEqual(self.down(), set())
                self.assert_pure(before)
                self.release((0, 0))
                self.step.assert_called_once_with(0, 0, Action.OPEN)
                self.assertEqual(self.engine.get_board_snapshot(), board)
                self.assertEqual(self.engine.get_observation(), obs)
                wasted["left"] += 1
                wasted["total"] += 1
                self.assertEqual(self.engine._wasted_clicks, wasted)
                self.assertEqual(self.engine._active_clicks, active)
                self.assertEqual(len(self.ui._replay_recorder.events), count + 1)
                self.assert_last_event("OPEN", (0, 0))
                self.assertEqual(self.signals, [("left", 0, 0)])
                self.assertEqual(self.down(), set())
                self.step.reset_mock()
                self.worker.reset_mock()
                self.signals.clear()

    def test_disabled_number_left_remains_ignored(self):
        self.prepare_numbers()
        self.ui.on_chord_mode_changed(ChordMode.DISABLED)
        for origin in ((0, 0), (4, 0)):
            with self.subTest(origin=origin):
                before = self.snapshot()
                self.press(origin)
                self.assertEqual(self.down(),
                                 {(4, 0)} if origin == (4, 0) else set())
                self.move((0, 0))
                self.assertEqual(self.down(), set())
                self.assert_pure(before)
                self.release((0, 0))
                self.assertEqual(self.snapshot(), before)
                self.step.assert_not_called()
                self.worker.assert_not_called()
                self.assertEqual(self.signals, [("left", 0, 0)])
                self.signals.clear()

    def check_both_order(self, first_press, first_release):
        self.prepare_numbers()
        self.ui.on_chord_mode_changed(ChordMode.BOTH_CLICK)
        before = self.snapshot()
        count = len(self.ui._replay_recorder.events)
        other_press = Qt.RightButton if first_press == Qt.LeftButton else Qt.LeftButton
        other_release = Qt.RightButton if first_release == Qt.LeftButton else Qt.LeftButton
        self.press((0, 0), first_press)
        self.press((0, 0), other_press)
        self.assertEqual(self.down(), self.neighbors((0, 0)))
        self.assert_pure(before)
        self.release((0, 0), first_release)
        self.step.assert_called_once_with(0, 0, Action.CHORD)
        self.assertEqual(self.signals, [("both", 0, 0)])
        self.assertEqual(len(self.ui._replay_recorder.events), count + 1)
        self.assert_last_event("CHORD", (0, 0))
        self.assertEqual(self.down(), set())
        after = self.snapshot()
        self.move((4, 0))
        self.assertEqual(self.down(), set())
        self.release((4, 0), other_release)
        self.assertEqual(self.snapshot(), after)
        self.assertEqual(self.step.call_count, 1)
        self.assertEqual(self.signals, [("both", 0, 0)])

    def test_both_left_right_release_left_right(self):
        self.check_both_order(Qt.LeftButton, Qt.LeftButton)

    def test_both_left_right_release_right_left(self):
        self.check_both_order(Qt.LeftButton, Qt.RightButton)

    def test_both_right_left_release_left_right(self):
        self.check_both_order(Qt.RightButton, Qt.LeftButton)

    def test_both_right_left_release_right_left(self):
        self.check_both_order(Qt.RightButton, Qt.RightButton)

    def test_both_is_allowed_in_left_click_mode(self):
        self.prepare_numbers()
        self.press((0, 0))
        self.press((0, 0), Qt.RightButton)
        self.assertEqual(self.down(), self.neighbors((0, 0)))
        self.release((0, 0))
        self.release((0, 0), Qt.RightButton)
        self.step.assert_called_once_with(0, 0, Action.CHORD)
        self.assertEqual(self.signals, [("both", 0, 0)])

    def test_disabled_both_never_previews_or_commits(self):
        self.prepare_numbers()
        self.ui.on_chord_mode_changed(ChordMode.DISABLED)
        for target in ((0, 0), (4, 0), (1, 1)):
            for first in (Qt.LeftButton, Qt.RightButton):
                with self.subTest(target=target, first=first):
                    second = (Qt.RightButton if first == Qt.LeftButton
                              else Qt.LeftButton)
                    before = self.snapshot()
                    self.press(target)
                    self.press(target, Qt.RightButton)
                    self.assertEqual(self.down(), set())
                    self.move((0, 0))
                    self.assertEqual(self.down(), set())
                    self.release(target, first)
                    self.assert_pure(before)
                    self.assertEqual(self.down(), set())
                    self.release((4, 0), second)
                    self.assert_pure(before)

    def test_both_first_release_outside_consumes_both_orders(self):
        self.prepare_numbers()
        for first in (Qt.LeftButton, Qt.RightButton):
            with self.subTest(first=first):
                second = Qt.RightButton if first == Qt.LeftButton else Qt.LeftButton
                before = self.snapshot()
                self.press((0, 0))
                self.press((0, 0), Qt.RightButton)
                self.release(self.outside(), first)
                self.assertEqual(self.down(), set())
                self.move((4, 0))
                self.release((4, 0), second)
                self.assert_pure(before)

    def test_both_preview_tracks_numbers_and_clears_on_invalid_targets(self):
        self.prepare_numbers()
        before = self.snapshot()
        self.press((4, 0), Qt.RightButton)
        self.press((4, 0))
        self.assertEqual(self.down(), set())
        for target in ((0, 0), (2, 0)):
            self.move(target)
            self.assertEqual(self.down(), self.neighbors(target))
            self.assert_pure(before)
        for target in ((4, 0), (1, 1), self.outside()):
            self.move(target)
            self.assertEqual(self.down(), set())
            self.assert_pure(before)
        self.move((0, 0))
        self.assertEqual(self.down(), self.neighbors((0, 0)))
        self.release((2, 0), Qt.RightButton)
        self.step.assert_called_once_with(2, 0, Action.CHORD)
        self.release((0, 0))
        self.assertEqual(self.step.call_count, 1)

    def check_wasted_both(self, mode, target):
        self.ui.on_chord_mode_changed(mode)
        # Exercise both a stationary BOTH and a BOTH dragged from a number,
        # in all four press/release orders.
        for origin in ((0, 0), target):
            for first_press in (Qt.LeftButton, Qt.RightButton):
                for first_release in (Qt.LeftButton, Qt.RightButton):
                    with self.subTest(origin=origin, first_press=first_press,
                                      first_release=first_release):
                        other_press = (Qt.RightButton
                                       if first_press == Qt.LeftButton
                                       else Qt.LeftButton)
                        other_release = (Qt.RightButton
                                         if first_release == Qt.LeftButton
                                         else Qt.LeftButton)
                        self.step.reset_mock()
                        self.worker.reset_mock()
                        self.signals.clear()
                        before = self.snapshot()
                        obs = self.engine.get_observation()
                        board = self.engine.get_board_snapshot()
                        wasted = self.engine._wasted_clicks.copy()
                        active = self.engine._active_clicks.copy()
                        count = len(self.ui._replay_recorder.events)
                        self.press(origin, first_press)
                        self.press(origin, other_press)
                        self.move(target)
                        if obs[target[1]][target[0]] in (
                                CellState.HIDDEN, CellState.FLAGGED):
                            self.assertEqual(self.down(), set())
                        self.assert_pure(before)
                        self.release(target, first_release)
                        self.step.assert_called_once_with(*target, Action.CHORD)
                        self.assertEqual(self.engine.get_observation(), obs)
                        self.assertEqual(self.engine.get_board_snapshot(), board)
                        wasted["chord"] += 1
                        wasted["total"] += 1
                        self.assertEqual(self.engine._wasted_clicks, wasted)
                        self.assertEqual(self.engine._active_clicks, active)
                        self.assertEqual(len(self.ui._replay_recorder.events),
                                         count + 1)
                        self.assert_last_event("CHORD", target)
                        self.assertEqual(self.signals, [("both", *target)])
                        self.assertEqual(self.down(), set())
                        after = self.snapshot()
                        self.move((4, 0))
                        self.assertEqual(self.down(), set())
                        self.release((4, 0), other_release)
                        self.assertEqual(self.snapshot(), after)
                        self.step.assert_called_once_with(*target, Action.CHORD)
                        self.assertEqual(self.signals, [("both", *target)])

    def test_left_mode_both_hidden_records_one_wasted_chord(self):
        self.prepare_numbers()
        self.check_wasted_both(ChordMode.LEFT_CLICK, (4, 0))

    def test_left_mode_both_flagged_records_one_wasted_chord(self):
        self.prepare_numbers()
        self.check_wasted_both(ChordMode.LEFT_CLICK, (1, 1))

    def test_both_mode_both_hidden_records_one_wasted_chord(self):
        self.prepare_numbers()
        self.check_wasted_both(ChordMode.BOTH_CLICK, (4, 0))

    def test_both_mode_both_flagged_records_one_wasted_chord(self):
        self.prepare_numbers()
        self.check_wasted_both(ChordMode.BOTH_CLICK, (1, 1))

    def test_both_failed_number_and_zero_record_one_wasted_chord(self):
        self.prepare_numbers(flag=False)
        self.ui.on_left_click(0, 4)
        self.assertEqual(self.engine.get_observation()[4][0], 0)
        for mode in (ChordMode.LEFT_CLICK, ChordMode.BOTH_CLICK):
            for target in ((0, 0), (0, 4)):
                with self.subTest(mode=mode, target=target):
                    self.check_wasted_both(mode, target)

    def test_hover_hidden_cell_has_exactly_normal_pixels(self):
        window = self.ui.windowHandle()
        for size in (10, 28, 60):
            with self.subTest(size=size):
                self.ui.on_cell_size_changed(size)
                self.app.processEvents()
                cell = self.ui._buttons[(0, 0)]
                QTest.mouseMove(window, self.window_point(self.outside()))
                self.app.processEvents()
                self.assertFalse(cell.underMouse())
                normal = cell.grab().toImage()
                QTest.mouseMove(window, self.window_point((0, 0)))
                self.app.processEvents()
                self.assertTrue(cell.underMouse())
                self.assertFalse(cell.isDown())
                self.assertEqual(cell.grab().toImage(), normal)
        self.step.assert_not_called()

    def test_drag_clears_origin_pixels_while_qt_keeps_mouse_grab(self):
        window = self.ui.windowHandle()
        origin = self.ui._buttons[(0, 0)]
        target = self.ui._buttons[(1, 0)]
        QTest.mouseMove(window, self.window_point(self.outside()))
        self.app.processEvents()
        normal = origin.grab().toImage()
        QTest.mouseMove(window, self.window_point((0, 0)))
        QTest.mousePress(window, Qt.LeftButton, pos=self.window_point((0, 0)))
        try:
            self.assertEqual(self.down(), {(0, 0)})
            self.assertNotEqual(origin.grab().toImage(), normal)
            QTest.mouseMove(window, self.window_point((1, 0)))
            self.app.processEvents()
            self.assertFalse(origin.isDown())
            self.assertTrue(target.isDown())
            self.assertEqual(self.down(), {(1, 0)})
            self.assertEqual(origin.grab().toImage(), normal)
            self.step.assert_not_called()
        finally:
            QTest.mouseRelease(window, Qt.LeftButton,
                               pos=self.window_point(self.outside()))

    def test_space_reset_clears_hover_pixels_before_physical_release(self):
        window = self.ui.windowHandle()
        origin = self.ui._buttons[(0, 0)]
        QTest.mouseMove(window, self.window_point(self.outside()))
        self.app.processEvents()
        normal = origin.grab().toImage()
        QTest.mouseMove(window, self.window_point((0, 0)))
        QTest.mousePress(window, Qt.LeftButton, pos=self.window_point((0, 0)))
        try:
            self.assertTrue(origin.isDown())
            self.assertNotEqual(origin.grab().toImage(), normal)
            QTest.keyClick(self.ui, Qt.Key_Space)
            self.app.processEvents()
            self.assertFalse(origin.isDown())
            self.assertEqual(self.down(), set())
            self.assertEqual(origin.grab().toImage(), normal)
            before_release = self.snapshot()
        finally:
            QTest.mouseRelease(window, Qt.LeftButton,
                               pos=self.window_point((0, 0)))
        self.assert_pure(before_release)

    def test_independent_right_flags_under_left_grab_then_left_opens(self):
        window = self.ui.windowHandle()
        origin = self.ui._buttons[(0, 0)]
        events = []
        origin.mouse_input.connect(
            lambda cell, e: events.append((cell, e.type(), e.button())))
        QTest.mousePress(window, Qt.LeftButton, pos=self.window_point((0, 0)))
        try:
            QTest.mouseMove(window, self.window_point((1, 1)))
            self.assertEqual(self.down(), {(1, 1)})
            QTest.mousePress(window, Qt.RightButton,
                             pos=self.window_point((1, 1)))
            try:
                self.assertFalse(self.ui._mouse_both)
                self.assertEqual(self.down(), {(1, 1)})
                self.step.assert_not_called()
            finally:
                QTest.mouseRelease(window, Qt.RightButton,
                                   pos=self.window_point((1, 1)))
            self.step.assert_called_once_with(1, 1, Action.FLAG)
            self.assert_click_totals(1, 0, 1, 0)
            self.assertEqual(self.signals, [("right", 1, 1)])
            self.assertEqual(self.engine.get_observation()[1][1],
                             CellState.FLAGGED)
            self.assertEqual(self.ui._mouse_buttons, Qt.LeftButton)
            self.assertFalse(self.ui._mouse_consumed)
            self.assertEqual(self.down(), set())
            QTest.mouseMove(window, self.window_point((2, 0)))
            self.assertEqual(self.down(), {(2, 0)})
        finally:
            QTest.mouseRelease(window, Qt.LeftButton,
                               pos=self.window_point((2, 0)))
        self.assertEqual(self.step.call_args_list,
                         [call(1, 1, Action.FLAG), call(2, 0, Action.OPEN)])
        self.assertEqual(self.signals, [("right", 1, 1), ("left", 2, 0)])
        self.assertEqual([(e.action, e.x, e.y)
                          for e in self.ui._replay_recorder.events],
                         [("FLAG", 1, 1), ("OPEN", 2, 0)])
        self.assertEqual(self.engine.get_observation()[0][0], CellState.HIDDEN)
        self.assertEqual(self.engine.get_observation()[0][2], 2)
        self.assert_click_totals(2, 1, 1, 0)
        self.assert_mouse_cleared()
        self.assertEqual(self.engine._wasted_clicks["chord"], 0)
        self.assertEqual(self.engine._active_clicks["chord"], 0)
        for kind in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
            self.assertIn((origin, kind, Qt.RightButton), events)
        self.assertEqual(self.down(), set())
        self.assertEqual(self.ui._mouse_buttons, Qt.NoButton)

    def test_new_flag_suppresses_held_left_release_in_every_chord_mode(self):
        window = self.ui.windowHandle()
        origin = self.ui._buttons[(0, 0)]
        events = []
        origin.mouse_input.connect(
            lambda cell, e: events.append((cell, e.type(), e.button())))
        for mode in ChordMode:
            # A different RIGHT origin proves it is the release target that
            # matters. Both cases still route through LEFT's original grab.
            for right_origin in ((1, 1), (2, 0)):
                with self.subTest(mode=mode, right_origin=right_origin):
                    self.ui.on_reset()
                    self.engine.reset_with_mines(
                        5, 5, 3, {(1, 1), (3, 1), (3, 3)})
                    self.ui.render_board()
                    self.ui.on_chord_mode_changed(mode)
                    self.step.reset_mock()
                    self.worker.reset_mock()
                    self.signals.clear()
                    events.clear()
                    QTest.mousePress(window, Qt.LeftButton,
                                     pos=self.window_point((0, 0)))
                    try:
                        QTest.mouseMove(window, self.window_point(right_origin))
                        QTest.mousePress(window, Qt.RightButton,
                                         pos=self.window_point(right_origin))
                        try:
                            self.assertFalse(self.ui._mouse_both)
                            self.step.assert_not_called()
                            QTest.mouseMove(window, self.window_point((1, 1)))
                        finally:
                            QTest.mouseRelease(window, Qt.RightButton,
                                               pos=self.window_point((1, 1)))
                        self.step.assert_called_once_with(1, 1, Action.FLAG)
                        self.assert_click_totals(1, 0, 1, 0)
                        self.assertEqual(self.ui._mouse_buttons, Qt.LeftButton)
                        self.assertEqual(self.ui._mouse_left_suppressed, {(1, 1)})
                        self.assertEqual(self.down(), set())
                        self.assertEqual(self.engine.get_observation()[1][1],
                                         CellState.FLAGGED)
                        after_flag = self.snapshot()
                    finally:
                        QTest.mouseRelease(window, Qt.LeftButton,
                                           pos=self.window_point((1, 1)))
                    self.assertEqual(self.snapshot(), after_flag)
                    self.step.assert_called_once_with(1, 1, Action.FLAG)
                    self.assertEqual(self.signals, [("right", 1, 1)])
                    self.assert_click_totals(1, 0, 1, 0)
                    self.assertEqual(self.engine._wasted_clicks["left"], 0)
                    self.assertEqual(
                        [(e.action, e.x, e.y)
                         for e in self.ui._replay_recorder.events],
                        [("FLAG", 1, 1)])
                    for kind in (QEvent.MouseButtonPress,
                                 QEvent.MouseButtonRelease):
                        self.assertIn((origin, kind, Qt.RightButton), events)
                    self.assert_mouse_cleared()

    def test_fresh_flagged_left_after_suppression_still_counts_wasted_open(self):
        self.flag_during_left_hold()
        self.release((1, 1))
        self.assert_click_totals(1, 0, 1, 0)
        self.assert_mouse_cleared()
        wasted = self.engine._wasted_clicks["left"]
        self.press((1, 1))
        self.assertEqual(self.down(), set())
        self.assertEqual(self.ui._mouse_left_suppressed, set())
        self.release((1, 1))
        self.assertEqual(self.step.call_args_list,
                         [call(1, 1, Action.FLAG), call(1, 1, Action.OPEN)])
        self.assertEqual(self.engine._wasted_clicks["left"], wasted + 1)
        self.assertEqual(self.engine.get_observation()[1][1], CellState.FLAGGED)
        self.assert_click_totals(2, 1, 1, 0)
        self.assertEqual([(e.action, e.x, e.y)
                          for e in self.ui._replay_recorder.events],
                         [("FLAG", 1, 1), ("OPEN", 1, 1)])
        self.assert_mouse_cleared()

    def test_unflag_during_same_left_hold_restores_normal_open(self):
        target = (1, 0)  # Safe so the final OPEN leaves the game running.
        self.flag_during_left_hold(target)
        self.assertEqual(self.ui._mouse_left_suppressed, {target})
        self.press(target, Qt.RightButton)
        self.release(target, Qt.RightButton)
        self.assertEqual(self.engine.get_observation()[0][1], CellState.HIDDEN)
        self.assertEqual(self.ui._mouse_left_suppressed, set())
        self.assertEqual(self.ui._mouse_buttons, Qt.LeftButton)
        self.assertEqual(self.down(), {target})
        self.release(target)
        self.assertEqual(self.step.call_args_list,
                         [call(1, 0, Action.FLAG), call(1, 0, Action.FLAG),
                          call(1, 0, Action.OPEN)])
        self.assertEqual([(e.action, e.x, e.y)
                          for e in self.ui._replay_recorder.events],
                         [("FLAG", 1, 0), ("FLAG", 1, 0), ("OPEN", 1, 0)])
        self.assertEqual(self.engine.get_observation()[0][1], 1)
        self.assertEqual(self.engine._wasted_clicks["left"], 0)
        self.assert_click_totals(3, 1, 2, 0)
        self.assert_mouse_cleared()

    def test_multiple_new_flags_are_remembered_for_one_left_hold(self):
        self.flag_during_left_hold()
        self.move((3, 1))
        self.press((3, 1), Qt.RightButton)
        self.release((3, 1), Qt.RightButton)
        self.assertEqual(self.ui._mouse_left_suppressed, {(1, 1), (3, 1)})
        self.move((1, 1))
        self.release((1, 1))
        self.assertEqual(self.step.call_args_list,
                         [call(1, 1, Action.FLAG), call(3, 1, Action.FLAG)])
        self.assertEqual([(e.action, e.x, e.y)
                          for e in self.ui._replay_recorder.events],
                         [("FLAG", 1, 1), ("FLAG", 3, 1)])
        self.assert_click_totals(2, 0, 2, 0)
        self.assert_mouse_cleared()

    def test_other_preexisting_flag_keeps_normal_left_release_policy(self):
        self.ui.on_right_click(3, 3)
        self.flag_during_left_hold()
        self.assertEqual(self.ui._mouse_left_suppressed, {(1, 1)})
        self.release((3, 3))
        self.assertEqual(self.step.call_args_list,
                         [call(3, 3, Action.FLAG), call(1, 1, Action.FLAG),
                          call(3, 3, Action.OPEN)])
        self.assertEqual(self.engine._wasted_clicks["left"], 1)
        self.assertEqual(self.engine.get_observation()[3][3], CellState.FLAGGED)
        self.assertEqual(len(self.ui._replay_recorder.events), 3)
        self.assert_last_event("OPEN", (3, 3))
        self.assert_click_totals(3, 1, 2, 0)
        self.assert_mouse_cleared()

    def test_remembered_flag_does_not_change_same_origin_both(self):
        for mode in ChordMode:
            with self.subTest(mode=mode):
                self.ui.on_reset()
                self.engine.reset_with_mines(
                    5, 5, 3, {(1, 1), (3, 1), (3, 3)})
                self.ui.render_board()
                self.ui.on_chord_mode_changed(mode)
                self.step.reset_mock()
                self.worker.reset_mock()
                self.signals.clear()
                self.flag_during_left_hold()
                self.move((0, 0))
                self.press((0, 0), Qt.RightButton)
                self.assertTrue(self.ui._mouse_both)
                self.release((1, 1))
                if mode == ChordMode.DISABLED:
                    self.step.assert_called_once_with(1, 1, Action.FLAG)
                    self.assert_click_totals(1, 0, 1, 0)
                    actions = ["FLAG"]
                else:
                    self.assertEqual(self.step.call_args_list,
                                     [call(1, 1, Action.FLAG),
                                      call(1, 1, Action.CHORD)])
                    self.assertEqual(self.engine._wasted_clicks["chord"], 1)
                    self.assert_click_totals(2, 0, 1, 1)
                    actions = ["FLAG", "CHORD"]
                after_first = self.snapshot()
                self.release((1, 1), Qt.RightButton)
                self.assertEqual(self.snapshot(), after_first)
                self.assertEqual([e.action for e in self.ui._replay_recorder.events],
                                 actions)
                self.assert_mouse_cleared()

    def check_flag_suppression_invalidation(self, invalidate):
        self.flag_during_left_hold()
        old = self.receiver
        self.assertEqual(self.ui._mouse_left_suppressed, {(1, 1)})
        invalidate()
        self.assert_mouse_cleared()
        self.step.reset_mock()
        self.worker.reset_mock()
        self.signals.clear()
        before = self.snapshot()
        self.release((1, 1), receiver=old)
        self.assert_pure(before)
        self.assert_mouse_cleared()

    def test_space_reset_clears_flag_suppression_and_stale_release(self):
        self.check_flag_suppression_invalidation(
            lambda: QTest.keyClick(self.ui, Qt.Key_Space))

    def test_rebuild_clears_flag_suppression_and_stale_release(self):
        self.check_flag_suppression_invalidation(
            lambda: self.ui._rebuild_game(9, 9, 10))

    def test_replay_transition_clears_flag_suppression_and_stale_release(self):
        player = ReplayPlayer(ReplayData(ReplayBoard(
            5, 5, 3, {(1, 1), (3, 1), (3, 3)}), ()))
        self.check_flag_suppression_invalidation(
            lambda: self.ui._enter_replay_mode(player))
        self.ui._exit_replay_mode()
        self.assert_mouse_cleared()

    def test_independent_left_opens_under_right_grab_then_right_flags(self):
        window = self.ui.windowHandle()
        origin = self.ui._buttons[(0, 0)]
        events = []
        origin.mouse_input.connect(
            lambda cell, e: events.append((cell, e.type(), e.button())))
        QTest.mousePress(window, Qt.RightButton, pos=self.window_point((0, 0)))
        try:
            QTest.mouseMove(window, self.window_point((1, 0)))
            QTest.mousePress(window, Qt.LeftButton,
                             pos=self.window_point((1, 0)))
            try:
                self.assertFalse(self.ui._mouse_both)
                self.assertEqual(self.down(), {(1, 0)})
                self.step.assert_not_called()
            finally:
                QTest.mouseRelease(window, Qt.LeftButton,
                                   pos=self.window_point((1, 0)))
            self.step.assert_called_once_with(1, 0, Action.OPEN)
            self.assertEqual(self.signals, [("left", 1, 0)])
            self.assertEqual(self.ui._mouse_buttons, Qt.RightButton)
            self.assertFalse(self.ui._mouse_consumed)
            self.assertEqual(self.down(), set())
            QTest.mouseMove(window, self.window_point((1, 1)))
        finally:
            QTest.mouseRelease(window, Qt.RightButton,
                               pos=self.window_point((1, 1)))
        self.assertEqual(self.step.call_args_list,
                         [call(1, 0, Action.OPEN), call(1, 1, Action.FLAG)])
        self.assertEqual(self.signals, [("left", 1, 0), ("right", 1, 1)])
        self.assertEqual([(e.action, e.x, e.y)
                          for e in self.ui._replay_recorder.events],
                         [("OPEN", 1, 0), ("FLAG", 1, 1)])
        self.assertEqual(self.engine.get_observation()[0][0], CellState.HIDDEN)
        self.assertEqual(self.engine.get_observation()[0][1], 1)
        self.assertEqual(self.engine.get_observation()[1][1], CellState.FLAGGED)
        for kind in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
            self.assertIn((origin, kind, Qt.LeftButton), events)
        self.assertEqual(self.down(), set())
        self.assertEqual(self.ui._mouse_buttons, Qt.NoButton)

    def test_different_origins_remain_independent_in_every_chord_mode(self):
        # Release the first-pressed button first as well; each remaining
        # gesture must stay live, regardless of the configured chord mode.
        for mode in ChordMode:
            for first in (Qt.LeftButton, Qt.RightButton):
                with self.subTest(mode=mode, first=first):
                    self.ui.on_reset()
                    self.engine.reset_with_mines(
                        5, 5, 3, {(1, 1), (3, 1), (3, 3)})
                    self.ui.render_board()
                    self.ui.on_chord_mode_changed(mode)
                    self.step.reset_mock()
                    self.worker.reset_mock()
                    self.signals.clear()
                    second = (Qt.RightButton if first == Qt.LeftButton
                              else Qt.LeftButton)
                    self.press((0, 0), first)
                    self.move((1, 0))
                    self.press((1, 0), second)
                    self.assertFalse(self.ui._mouse_both)
                    first_target = (2, 0) if first == Qt.LeftButton else (1, 1)
                    self.release(first_target, first)
                    self.assertEqual(self.ui._mouse_buttons, second)
                    self.assertFalse(self.ui._mouse_consumed)
                    self.move((3, 0))
                    self.assertEqual(self.down(),
                                     {(3, 0)} if second == Qt.LeftButton
                                     else set())
                    self.release((3, 0), second)
                    first_action = (Action.OPEN if first == Qt.LeftButton
                                    else Action.FLAG)
                    second_action = (Action.OPEN if second == Qt.LeftButton
                                     else Action.FLAG)
                    self.assertEqual(self.step.call_args_list,
                                     [call(*first_target, first_action),
                                      call(3, 0, second_action)])
                    self.assertNotIn("both", [s[0] for s in self.signals])
                    self.assertEqual(
                        [e.action for e in self.ui._replay_recorder.events],
                        ["OPEN", "FLAG"] if first == Qt.LeftButton
                        else ["FLAG", "OPEN"])

    def test_keyboard_reset_invalidates_old_release_and_allows_fresh_gesture(self):
        self.press((0, 0))
        self.assertTrue(self.down())
        token = self.ui._zini_job_token
        QTest.keyClick(self.ui, Qt.Key_Space)
        self.assertGreater(self.ui._zini_job_token, token)
        self.assertEqual(self.down(), set())
        before = self.snapshot()
        self.release((1, 0))
        self.assert_pure(before)
        self.press((1, 0))
        self.release((1, 0))
        self.step.assert_called_once_with(1, 0, Action.OPEN)

    def test_second_press_after_reset_cannot_revive_stale_hold(self):
        self.press((0, 0))
        self.ui.on_reset()
        before = self.snapshot()
        self.press((1, 0), Qt.RightButton)
        self.move((1, 0))
        self.release((1, 0))
        self.release((1, 0), Qt.RightButton)
        self.assert_pure(before)
        self.assertEqual(self.down(), set())

    def test_difficulty_rebuild_rejects_old_and_new_widget_stale_releases(self):
        self.press((0, 0))
        old = self.receiver
        self.ui.on_difficulty_changed("초급 (9x9, 10)")
        self.assertEqual((self.engine.width, self.engine.height), (9, 9))
        self.assertFalse(old.isDown())
        before = self.snapshot()
        self.release((0, 0), receiver=old)
        self.release((1, 0), receiver=self.ui._buttons[(1, 0)])
        self.assert_pure(before)
        self.assertEqual(self.down(), set())

    def test_replay_entry_exit_block_live_mouse_and_stale_releases(self):
        self.press((0, 0))
        old = self.receiver
        player = ReplayPlayer(ReplayData(ReplayBoard(5, 5, 3,
                                                    {(1, 1), (3, 1), (3, 3)}), ()))
        self.ui._enter_replay_mode(player)
        self.assertFalse(old.isDown())
        before = self.snapshot()
        self.release((0, 0), receiver=old)
        self.press((1, 0))
        self.release((1, 0))
        self.assert_pure(before)
        self.assertEqual(self.down(), set())
        self.press((1, 0))
        self.ui._exit_replay_mode()
        before = self.snapshot()
        self.release((1, 0), receiver=self.ui._buttons[(1, 0)])
        self.assert_pure(before)

    def test_close_clears_preview_and_rejects_old_release(self):
        self.press((0, 0))
        self.ui.close()
        self.assertEqual(self.down(), set())
        before = self.snapshot()
        self.release((0, 0))
        self.assert_pure(before)

    def test_qtest_double_click_is_a_second_release_committed_click(self):
        cell = self.ui._buttons[(0, 0)]
        QTest.mouseClick(cell, Qt.LeftButton)
        self.assertEqual(self.step.call_count, 1)
        before = self.snapshot()
        QTest.mouseDClick(cell, Qt.LeftButton)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.step.call_count, 1)
        self.assertEqual(self.down(), self.neighbors((0, 0)))
        QTest.mouseRelease(cell, Qt.LeftButton)
        self.assertEqual(self.step.call_count, 2)
        self.assertEqual([e.action for e in self.ui._replay_recorder.events],
                         ["OPEN", "CHORD"])
        self.assertEqual(self.down(), set())

    def test_rapid_right_double_click_toggles_once_per_release(self):
        cell = self.ui._buttons[(1, 1)]
        QTest.mouseClick(cell, Qt.RightButton)
        QTest.mouseDClick(cell, Qt.RightButton)
        self.assertEqual(self.step.call_count, 1)
        self.assertEqual(self.engine.get_observation()[1][1], CellState.FLAGGED)
        QTest.mouseRelease(cell, Qt.RightButton)
        self.assertEqual(self.step.call_count, 2)
        self.assertEqual(self.engine.get_observation()[1][1], CellState.HIDDEN)

    def test_pressed_presentation_changes_pixels_and_restores_at_all_sizes(self):
        for size in (10, 28, 60):
            with self.subTest(size=size):
                self.ui.on_cell_size_changed(size)
                self.app.processEvents()
                cell = self.ui._buttons[(0, 0)]
                normal = cell.grab().toImage()
                self.press((0, 0))
                self.assertTrue(cell.isDown())
                self.assertNotEqual(cell.grab().toImage(), normal)
                self.release(self.outside())
                self.assertEqual(cell.grab().toImage(), normal)
        self.step.assert_not_called()

    def test_scroll_offset_and_viewport_clipping_resolve_visible_target(self):
        self.ui._rebuild_game(50, 50, 10)
        self.ui.resize(1000, 650)
        self.app.processEvents()
        self.ui.scroll_area.horizontalScrollBar().setValue(280)
        self.ui.scroll_area.verticalScrollBar().setValue(280)
        self.app.processEvents()
        before = self.snapshot()
        self.press((11, 11))
        self.move((12, 11))
        self.assertEqual(self.down(), {(12, 11)})
        # This coordinate belongs to a board cell, but is clipped by viewport.
        self.move((0, 0))
        self.assertEqual(self.down(), set())
        self.assert_pure(before)
        self.move((12, 11))
        self.assertEqual(self.down(), {(12, 11)})
        self.release((12, 11))
        self.step.assert_called_once_with(12, 11, Action.OPEN)


if __name__ == "__main__":
    unittest.main()
