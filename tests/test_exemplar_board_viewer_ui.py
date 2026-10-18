"""Bounded synthetic offscreen inspection; no official DB or solver fixtures."""

import ast
from contextlib import ExitStack, redirect_stderr
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction
import inspect
import io
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from qt_bootstrap import configure_qt_plugin_path
configure_qt_plugin_path()

from PyQt5.QtCore import QEvent, QPoint, QPointF, QRect, Qt, QTimer
from PyQt5.QtGui import QFontDatabase, QMouseEvent
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QLabel, QPushButton, QSpinBox, QStyle, QStyleOptionSlider, QStyleOptionSpinBox

import benchmark_modeled_time as modeled
from core_engine import Action, CellState, GameStatus, MinesweeperEngine
from exemplar_board_evidence import AcceptedExemplarEvidence, ExemplarReference, LoadedExemplar
import exemplar_board_evidence as evidence_module
from exemplar_board_reconstruction import reconstruct_board
import exemplar_board_reconstruction as reconstruction_module
import exemplar_board_viewer_ui as ui
from scripts import exemplar_board_viewer as launcher
from telemetry_model import InferenceCategory
import telemetry_repository
import timeline_analytics
from tests import test_exemplar_board_reconstruction as fixtures


RISK = Fraction(10**50 + 1, 3 * 10**50)


def synthetic_evidence():
    """Real immutable models from hand-written inputs on small synthetic boards."""
    fixture = fixtures.ExemplarBoardReconstructionTests()
    fixture.evaluation = modeled.authenticate_model_c()
    board, stage3 = fixture.win()
    safe = [(0, 0), (1, 0), (0, 1), (2, 0), (2, 1), (0, 2), (1, 2), (2, 2)]
    events = [fixtures.event(0, Action.OPEN, 0, 0, safe=1),
              fixtures.event(1, Action.FLAG, 1, 1, flag=1)]
    for x, y in safe[1:]:
        events.append(fixtures.event(len(events), Action.OPEN, x, y, safe=1,
            status=GameStatus.WON if (x, y) == safe[-1] else GameStatus.PLAYING))
    events[2] = replace(events[2], inference_category=InferenceCategory.PROBABILITY_GUESS,
                        target_mine_probability=RISK, minimum_available_mine_probability=Fraction(1, 3),
                        selection_candidate_count=4, decision_compute_ns=0)
    stage2 = fixture.timeline(board, tuple(events))
    s3_events = [item.event for item in stage3.actions]
    s3_events[3] = replace(s3_events[3], inference_category=InferenceCategory.PROBABILITY_GUESS,
                          target_mine_probability=RISK, minimum_available_mine_probability=Fraction(1, 3),
                          decision_compute_ns=0)
    stage3 = fixture.timeline(board, tuple(s3_events))
    loss_board, loss = fixture.loss()
    flood_board, flood = fixture.flood_clear()
    auto_events = tuple(fixtures.event(i, Action.OPEN, x, y, safe=1,
        status=GameStatus.WON if i == len(safe) - 1 else GameStatus.PLAYING)
        for i, (x, y) in enumerate(safe))
    auto = fixture.timeline(board, auto_events)
    games = []
    for index, snapshot, s2, s3 in ((10, board, stage2, stage3), (20, loss_board, loss, loss),
                                    (30, flood_board, flood, flood), (40, board, auto, auto)):
        s2, s3 = (replace(timeline, record=replace(timeline.record, game_index=index, seed=index))
                  for timeline in (s2, s3))
        reference = ExemplarReference(index, f'Synthetic <category> {index}', s2.record.board_fingerprint,
            len(s2.actions), len(s3.actions), s2.total_modeled_us, s3.total_modeled_us, s2.record.result)
        games.append(LoadedExemplar(reference, snapshot, reconstruct_board(snapshot, s2),
                                    reconstruct_board(snapshot, s3)))
    return AcceptedExemplarEvidence((), (), fixture.evaluation, tuple(games),
                                    'synthetic-source', False, 'synthetic-python', 'synthetic-architecture')


class FakeZiniJob:
    """Controllable transport; no subprocess or algorithm in Viewer tests."""
    def __init__(self):
        self.starts = []
        self.closes = 0
        self.cancelled = []
        self.active = False
        self.token = None
        self.result = None

    def start(self, snapshot, token):
        self.starts.append((snapshot, token))
        self.token, self.active = token, True
        self.result = None

    def close(self):
        self.closes += 1
        if self.active:
            self.cancelled.append(self.token)
        self.active = False
        self.result = None

    def poll(self):
        result, self.result = self.result, None
        if result is not None:
            self.active = False
        return result

    def finish(self, clicks=5, **overrides):
        self.result = dict(token=self.token, clicks=clicks, error=None, **overrides)


class FakeWallClock:
    """Deterministic monotonic-clock seam; timer/UI wiring remains real Qt."""
    def __init__(self):
        self.ns = 0

    def start(self):
        self.ns = 0

    def invalidate(self):
        pass

    def nsecsElapsed(self):
        return self.ns


class ViewerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        # Windows' offscreen plugin has no system-font discovery. Register a
        # system font in this test process so pixel checks actually draw glyphs.
        cls._test_font_id = -1
        if sys.platform == 'win32' and not QFontDatabase().families():
            font = Path(os.environ['WINDIR']) / 'Fonts' / 'arial.ttf'
            cls._test_font_id = QFontDatabase.addApplicationFont(str(font))
            if cls._test_font_id < 0:
                raise RuntimeError('Offscreen pixel verification requires the system Arial font.')
        cls.bundle = synthetic_evidence()

    @classmethod
    def tearDownClass(cls):
        if cls._test_font_id >= 0:
            QFontDatabase.removeApplicationFont(cls._test_font_id)

    def setUp(self):
        job_patch = patch.object(ui, 'ZiniMetricJob', FakeZiniJob)
        job_patch.start()
        self.addCleanup(job_patch.stop)
        self.window = ui.ExemplarBoardViewerWindow(self.bundle)
        self.window._wall_clock = FakeWallClock()
        self.window.show()
        self.app.processEvents()
        self.addCleanup(self.cleanup_window)

    def cleanup_window(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def texts(self, values):
        return {name: label.text() for name, label in values.items()}

    def cell_state(self, cell):
        return (cell.logical_state, cell.text(), cell.styleSheet(), cell.toolTip(),
                cell.accessibleName(), cell.accessibleDescription(), cell.answer_layer.glyph)

    def assert_frame(self):
        frame = self.window.reconstruction.frames[self.window.position.frame_index]
        for (x, y), cell in self.window.board.cells.items():
            self.assertEqual(cell.logical_state, frame.observation[y][x])
        self.assertIn(frame.status.name, self.window.status_label.text())

    def focus_entry(self, entry):
        self.window.activateWindow()
        QTest.mouseClick(entry.lineEdit(), Qt.LeftButton)
        self.app.processEvents()
        self.assertTrue(entry.hasFocus() or entry.lineEdit().hasFocus())

    def type_entry(self, entry, text):
        self.focus_entry(entry)
        QTest.keyClick(entry.lineEdit(), Qt.Key_A, Qt.ControlModifier)
        QTest.keyClicks(entry.lineEdit(), text)
        self.app.processEvents()

    def click_answer_checkbox(self):
        checkbox = self.window.answer_checkbox
        QTest.mouseClick(checkbox, Qt.LeftButton, pos=QPoint(8, checkbox.height() // 2))
        self.app.processEvents()
        self.assertTrue(checkbox.hasFocus())

    def time_mode(self):
        clock = FakeWallClock()
        self.window._wall_clock = clock
        self.window.playback_mode.setCurrentText('Model C Time')
        return clock

    def index_tick(self, window=None):
        w = window or self.window
        if not isinstance(w._wall_clock, FakeWallClock):
            w._wall_clock = FakeWallClock()
        w._wall_clock.ns += w.index_interval.value() * 1_000_000
        w._advance_playback()

    def test_input_requires_exact_bundle_family_and_four_distinct_games(self):
        for value in (None, object(), self.bundle.exemplars, replace(self.bundle, exemplars=()),
                      replace(self.bundle, exemplars=(self.bundle.exemplars[0],) * 4)):
            with self.subTest(value=type(value)), self.assertRaises(ValueError):
                ui.ExemplarBoardViewerWindow(value)

    def test_four_game_two_solver_choices_and_exact_bundle_retained(self):
        self.assertIs(self.window.evidence, self.bundle)
        self.assertEqual([self.window.game_selector.itemData(i) for i in range(4)], [10, 20, 30, 40])
        self.assertEqual(self.window.solver_selector.count(), 2)
        self.assertFalse(self.window.game_selector.isEditable())
        self.assertEqual(len(self.window._positions), 8)

    def test_all_eight_positions_start_at_initial_frame(self):
        for game in self.bundle.exemplars:
            for solver in ('stage2', 'stage3'):
                self.window.select_pair(game.reference.game_index, solver)
                self.assertEqual(self.window.position.frame_index, 0)
                self.assertIsNone(self.window.position.action_ordinal)
                self.assertEqual(self.window.action_label.text(), 'Selected action = none')
                self.assert_frame()

    def test_all_eight_positions_restore_exact_action_and_side(self):
        expected = {}
        for i, pair in enumerate(self.window._positions):
            self.window.select_pair(*pair)
            j = min(1 + i, self.window.action_count)
            self.window.select_action(j)
            self.window.set_before(bool(i % 2))
            expected[pair] = self.window.position
        for pair in reversed(expected):
            self.window.select_pair(*pair)
            self.assertEqual(self.window.position, expected[pair])
            self.assert_frame()
        # S2's index 9 is not clamped when visiting S3's shorter stream.
        self.window.select_pair(10, 'stage2')
        self.window.select_frame(9)
        self.window.select_pair(10, 'stage3')
        self.assertEqual(self.window.action_count, 8)
        self.window.select_pair(10, 'stage2')
        self.assertEqual(self.window.position.frame_index, 9)

    def test_selector_widgets_restore_positions(self):
        self.window.select_action(3)
        self.window.set_before(True)
        self.window.solver_selector.setCurrentIndex(1)
        self.window.select_frame(5)
        self.window.game_selector.setCurrentIndex(1)
        self.assertEqual(self.window.position.frame_index, 0)
        self.window.game_selector.setCurrentIndex(0)
        self.assertEqual(self.window.position.frame_index, 5)
        self.window.solver_selector.setCurrentIndex(0)
        self.assertEqual(self.window.position.action_ordinal, 3)
        self.assertTrue(self.window.position.before)

    def test_first_previous_next_last_and_boundary_buttons(self):
        w = self.window
        self.assertFalse(w.first_button.isEnabled())
        self.assertFalse(w.previous_button.isEnabled())
        self.assertFalse(w.before_button.isEnabled())
        self.assertFalse(w.after_button.isEnabled())
        w.next_button.click()
        self.assertEqual(w.position.frame_index, 1)
        w.last_button.click()
        self.assertEqual(w.position.frame_index, w.action_count)
        self.assertFalse(w.next_button.isEnabled())
        self.assertFalse(w.last_button.isEnabled())
        w.previous_button.click()
        self.assertEqual(w.position.frame_index, w.action_count - 1)
        w.first_button.click()
        self.assertIsNone(w.position.action_ordinal)

    def test_frame_slider_and_single_direct_action_entry(self):
        w = self.window
        self.assertEqual((w.frame_slider.minimum(), w.frame_slider.maximum()), (0, 9))
        w.frame_slider.setValue(4)
        self.assertEqual((w.position.action_ordinal, w.position.before), (4, False))
        self.assertCountEqual(w.findChildren(QSpinBox), [w.index_interval, w.action_entry])
        self.assertFalse(hasattr(w, 'frame_entry'))
        self.assertFalse(hasattr(w, 'frame_go'))
        self.assertNotIn('Go frame', [button.text() for button in w.findChildren(QPushButton)])
        self.assertEqual((w.action_entry.minimum(), w.action_entry.maximum()), (1, 9))
        self.type_entry(w.action_entry, '6')
        self.assertEqual(w.position.action_ordinal, 4)
        with patch.object(w, 'select_action', wraps=w.select_action) as select:
            QTest.mouseClick(w.action_go, Qt.LeftButton)
            self.app.processEvents()
        select.assert_called_once_with(6)
        self.assertEqual(w.position.action_ordinal, 6)
        self.assertFalse(w.position.before)

    def test_slider_distant_track_click_seeks_directly_and_stops_playback(self):
        w = self.window
        slider = w.frame_slider
        slider.setPageStep(1)  # A page-step implementation would only reach 1.
        w.play_button.click()
        QTest.mouseClick(slider, Qt.LeftButton,
                         pos=QPoint(slider.width() * 4 // 5, slider.height() // 2))
        self.app.processEvents()
        self.assertIn(w.position.frame_index, (7, 8))
        self.assertFalse(w.position.before)
        self.assertFalse(w.play_timer.isActive())

    def test_slider_handle_drag_retains_native_behavior(self):
        w = self.window
        slider = w.frame_slider
        option = QStyleOptionSlider()
        slider.initStyleOption(option)
        handle = slider.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, slider)
        w.play_button.click()
        QTest.mousePress(slider, Qt.LeftButton, pos=handle.center())
        self.assertTrue(slider.isSliderDown())
        self.assertFalse(w.play_timer.isActive())
        target = QPoint(slider.width() * 2 // 3, handle.center().y())
        # The offscreen platform does not retain QTest's pressed-button state
        # for mouseMove. Deliver that move with the actual held-button mask.
        QApplication.sendEvent(slider, QMouseEvent(QEvent.MouseMove, QPointF(target),
            Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
        QTest.mouseRelease(slider, Qt.LeftButton, pos=target)
        self.app.processEvents()
        self.assertFalse(slider.isSliderDown())
        self.assertIn(w.position.frame_index, (5, 6, 7))

    def test_play_pause_real_timer_initial_advance_and_pause(self):
        from PyQt5.QtCore import QElapsedTimer
        from PyQt5.QtTest import QSignalSpy
        w = self.window
        w._wall_clock = QElapsedTimer()
        self.assertEqual(w.play_timer.interval(), 16)
        self.assertEqual(w.play_timer.timerType(), Qt.PreciseTimer)
        spy = QSignalSpy(w.play_timer.timeout)
        QTest.mouseClick(w.play_button, Qt.LeftButton)
        self.assertEqual(w.play_button.text(), 'Pause')
        for _ in range(30):
            self.assertTrue(spy.wait(1000))
            if w.position.frame_index:
                break
        QTest.mouseClick(w.play_button, Qt.LeftButton)
        self.assertEqual(w.position, ui._Position(1))
        self.assertEqual(w.play_button.text(), 'Play')
        self.assertFalse(w.play_timer.isActive())
        QTest.qWait(230)
        self.assertEqual(w.position, ui._Position(1))

    def test_playback_before_then_after_and_terminal_stop(self):
        w = self.window
        w.select_action(3)
        w.set_before(True)
        w.play_button.click()
        self.index_tick(w)
        self.assertEqual(w.position, ui._Position(3))
        self.index_tick(w)
        self.assertEqual(w.position, ui._Position(4))
        while w.play_timer.isActive():
            self.index_tick(w)
        self.assertEqual(w.position, ui._Position(w.action_count))
        self.assertFalse(w.play_button.isEnabled())
        w.play_button.click()
        self.assertFalse(w.play_timer.isActive())
        position = w.position
        self.index_tick(w)
        self.assertEqual(w.position, position)

    def test_every_manual_navigation_stops_playback(self):
        w = self.window
        commands = (
            w.first_button.click, w.previous_button.click, w.next_button.click,
            w.last_button.click, w.before_button.click,
            lambda: w.frame_slider.setValue(1),
            lambda: QTest.keyClick(w.action_entry, Qt.Key_Return),
            lambda: QTest.keyClick(w.action_entry, Qt.Key_Enter), w.action_go.click,
            lambda: w.game_selector.setCurrentIndex(1),
            lambda: w.solver_selector.setCurrentIndex(1),
            lambda: w.select_pair(20, 'stage2'),
        )
        for command in commands:
            with self.subTest(command=command):
                w.select_pair(10, 'stage2')
                w.select_action(3)
                w.play_button.click()
                self.assertTrue(w.play_timer.isActive())
                command()
                self.assertFalse(w.play_timer.isActive())
        w.select_pair(10, 'stage2')
        w.select_action(3)
        w.set_before(True)
        w.play_button.click()
        w.after_button.click()
        self.assertFalse(w.play_timer.isActive())
        self.assertEqual(w.position, ui._Position(3))

    def test_pair_switch_preserves_playback_position_and_overlay_does_not_stop(self):
        w = self.window
        expected = {}
        for pair in w._positions:
            w.select_pair(*pair)
            w.play_button.click()
            self.index_tick(w)
            w.answer_checkbox.setChecked(not w.answer_checkbox.isChecked())
            self.assertTrue(w.play_timer.isActive())
            expected[pair] = w.position
        for pair in expected:
            w.select_pair(*pair)
            self.assertFalse(w.play_timer.isActive())
            self.assertEqual(w.position, expected[pair])

    def test_close_stops_playback(self):
        self.window.play_button.click()
        self.window.close()
        self.assertFalse(self.window.play_timer.isActive())

    def test_playback_controls_defaults_bounds_and_mode_ownership(self):
        w = self.window
        self.assertEqual([w.playback_mode.itemText(i) for i in range(2)], ['Index', 'Model C Time'])
        self.assertEqual((w.index_interval.minimum(), w.index_interval.maximum(), w.index_interval.value()),
                         (20, 5000, 200))
        self.assertEqual(w.index_interval.suffix(), ' ms')
        self.assertEqual((w.playback_speed.minimum(), w.playback_speed.maximum(),
                          w.playback_speed.singleStep(), w.playback_speed.value()), (0.25, 8, 0.25, 1))
        self.assertEqual(w.playback_speed.suffix(), 'x')
        self.assertTrue(w.index_interval.isEnabled())
        self.assertFalse(w.playback_speed.isEnabled())
        self.assertEqual(w.playback_status.text(), 'Index — 200 ms/action')
        self.time_mode()
        self.assertFalse(w.index_interval.isEnabled())
        self.assertTrue(w.playback_speed.isEnabled())
        self.assertEqual(w.play_timer.interval(), 16)

    def test_active_index_interval_change_preserves_position_and_single_steps(self):
        w = self.window
        w.select_action(3)
        w.set_before(True)
        w.play_button.click()
        for interval, ordinal in ((20, 3), (5000, 4), (275, 5)):
            position = w.position
            w.index_interval.setValue(interval)
            self.assertTrue(w.play_timer.isActive())
            self.assertEqual(w._index_interval_ms, interval)
            self.assertEqual(w.position, position)
            self.index_tick(w)
            self.assertEqual(w.position, ui._Position(ordinal))
            self.assertEqual(w.playhead_us, w.reconstruction.timeline.actions[ordinal - 1].cumulative_modeled_us)

    def test_index_max_display_bounds_and_native_arrow_steps(self):
        w, entry = self.window, self.window.index_interval
        self.assertEqual((entry.minimum(), entry.maximum(), entry.value()), (20, 5000, 200))
        self.assertEqual(entry.text(), '200 ms')
        entry.setValue(20)
        self.assertEqual(entry.text(), 'Max (20 ms)')
        self.assertEqual(w.playback_status.text(), 'Index — Max (20 ms/action)')
        self.focus_entry(entry)
        QTest.keyClick(entry, Qt.Key_Down)
        self.assertEqual((entry.value(), entry.text()), (20, 'Max (20 ms)'))
        QTest.keyClick(entry, Qt.Key_Up)
        self.assertEqual((entry.value(), entry.text()), (21, '21 ms'))
        self.assertEqual(w.playback_status.text(), 'Index — 21 ms/action')
        entry.setValue(0)
        self.assertEqual(entry.value(), 20)
        entry.setValue(5001)
        self.assertEqual(entry.value(), 5000)

    def test_index_integer_text_commits_clamp_with_return_enter_and_focus_loss(self):
        w, entry = self.window, self.window.index_interval
        for typed, expected in (('5', 20), ('19', 20), ('-21', 20), ('5001', 5000), ('99999', 5000)):
            for commit in ('return', 'enter', 'focus'):
                with self.subTest(typed=typed, commit=commit):
                    entry.setValue(200)
                    self.type_entry(entry, typed)
                    self.assertIn(typed, entry.text())  # Do not silently drop sign/digits.
                    self.assertEqual(entry.value(), 200)  # Uncommitted input is not timer authority.
                    if commit == 'focus':
                        self.click_answer_checkbox()
                    else:
                        QTest.keyClick(entry, Qt.Key_Return if commit == 'return' else Qt.Key_Enter)
                    self.assertEqual(entry.value(), expected)
                    self.assertEqual(entry.text(), 'Max (20 ms)' if expected == 20 else '5000 ms')
                    self.assertEqual(w._index_interval_ms, expected)
                    self.assertTrue(20 <= w._index_interval_ms <= 5000)
                    self.assertEqual(w.position, ui._Position())

    def test_active_index_below_min_commit_and_step_up_keep_one_action_per_tick(self):
        w, entry = self.window, self.window.index_interval
        entry.setValue(5000)
        w.select_action(3)
        w.set_before(True)
        w.play_button.click()
        self.type_entry(entry, '5')
        before = w.position
        QTest.keyClick(entry, Qt.Key_Return)
        self.assertEqual(entry.text(), 'Max (20 ms)')
        self.assertEqual(w.play_timer.interval(), 16)
        self.assertTrue(w.play_timer.isActive())
        self.assertEqual(w.position, before)
        self.index_tick(w)
        self.assertEqual(w.position, ui._Position(3))
        QTest.keyClick(entry, Qt.Key_Up)
        self.assertEqual(w._index_interval_ms, 21)
        self.assertEqual(w.position, ui._Position(3))
        self.index_tick(w)
        self.assertEqual(w.position, ui._Position(4))
        entry.setValue(20)
        for ordinal in range(5, w.action_count + 1):
            self.index_tick(w)
            self.assertEqual(w.position, ui._Position(ordinal))
        self.assertFalse(w.play_timer.isActive())

    def test_index_max_configuration_does_not_touch_active_model_time(self):
        w, clock = self.window, self.time_mode()
        w.playback_speed.setValue(2)
        w.select_time(200123)
        w.play_button.click()
        clock.ns = 10000000
        w._advance_playback()
        state = (w.position, w.playhead_us, w._anchor_model_us, clock.ns)
        with patch.object(w.play_timer, 'start', side_effect=AssertionError('restart')), \
             patch.object(w.play_timer, 'setInterval', side_effect=AssertionError('change tick')):
            for value in (20, 21, 5000):
                w.index_interval.setValue(value)
                self.assertEqual((w.position, w.playhead_us, w._anchor_model_us, clock.ns), state)
                self.assertFalse(w.index_interval.isEnabled())
                self.assertEqual(w.playback_speed.value(), 2)
                self.assertTrue(w.play_timer.isActive())
                self.assertEqual(w.play_timer.interval(), 16)
                self.assertNotIn('Max', w.playback_status.text())

    def test_model_time_exact_boundaries_and_unequal_action_delays(self):
        w, clock = self.window, self.time_mode()
        actions = w.reconstruction.timeline.actions
        self.assertNotEqual(actions[0].modeled_action_us, actions[1].modeled_action_us)
        w.play_button.click()
        for ordinal, action in enumerate(actions, 1):
            clock.ns = (action.cumulative_modeled_us - 1) * 1000
            w._advance_playback()
            self.assertEqual(w.position.frame_index, ordinal - 1)
            self.assertTrue(w.play_timer.isActive())
            clock.ns += 1000
            w._advance_playback()
            self.assertEqual(w.position, ui._Position(ordinal))
        self.assertEqual(w.playhead_us, w.reconstruction.timeline.total_modeled_us)
        self.assertFalse(w.play_timer.isActive())
        self.assertEqual(w.play_button.text(), 'Play')

    def test_model_time_tick_crosses_all_due_actions_and_clamps_terminal(self):
        w, clock = self.window, self.time_mode()
        w.play_button.click()
        clock.ns = (w.reconstruction.timeline.actions[4].cumulative_modeled_us + 1) * 1000
        w._advance_playback()
        self.assertEqual(w.position, ui._Position(5))
        clock.ns = 10**15
        w._advance_playback()
        self.assertEqual(w.position, ui._Position(w.action_count))
        self.assertEqual(w.playhead_us, w.reconstruction.timeline.total_modeled_us)
        self.assertFalse(w.play_timer.isActive())
        self.assertFalse(w.play_button.isEnabled())
        w._advance_playback()
        self.assertEqual(w.playhead_us, w.reconstruction.timeline.total_modeled_us)

    def test_model_time_quarter_speed_scaling_uses_integer_microseconds(self):
        w, clock = self.window, self.time_mode()
        for speed, expected in ((0.25, 10000), (1, 40000), (2, 80000), (8, 320000)):
            with self.subTest(speed=speed):
                w.select_frame(0)
                w.playback_speed.setValue(speed)
                w.play_button.click()
                clock.ns = 40000000
                w._advance_playback()
                self.assertEqual(w.playhead_us, expected)
                self.assertIs(type(w.playhead_us), int)
                self.assertEqual(w.frame_slider.value(), expected)
        w.select_frame(0)
        w.playback_speed.setValue(0.25)
        w.play_button.click()
        clock.ns = 7999
        w._advance_playback()
        self.assertEqual(w.playhead_us, 1)  # Fractional us is presentation-driver truncation only.

    def test_active_speed_change_captures_old_speed_and_reanchors_without_jump(self):
        w, clock = self.window, self.time_mode()
        w.play_button.click()
        clock.ns = 240123000
        w.playback_speed.setValue(2)
        self.assertEqual(w.playhead_us, 240123)
        self.assertEqual(clock.ns, 0)
        self.assertTrue(w.play_timer.isActive())
        clock.ns = 10000000
        w._advance_playback()
        self.assertEqual(w.playhead_us, 260123)
        w.playback_speed.setValue(0.25)
        self.assertEqual(w.playhead_us, 260123)
        clock.ns = 40000000
        w._advance_playback()
        self.assertEqual(w.playhead_us, 270123)

    def test_model_time_pause_resume_keeps_exact_between_action_playhead(self):
        w, clock = self.window, self.time_mode()
        w.play_button.click()
        clock.ns = 200123000
        w._advance_playback()
        self.assertEqual(w.position, ui._Position(1))
        clock.ns = 250123000  # Capture even the wall time since the last UI tick.
        w.play_button.click()
        self.assertFalse(w.play_timer.isActive())
        self.assertEqual(w.playhead_us, 250123)
        w.play_button.click()
        self.assertEqual(clock.ns, 0)
        self.assertEqual(w.playhead_us, 250123)
        clock.ns = 10000
        w._advance_playback()
        self.assertEqual(w.playhead_us, 250133)
        self.assertEqual(w.position, ui._Position(1))

    def test_model_time_before_waits_for_selected_action_cost(self):
        w, clock = self.window, self.time_mode()
        w.select_action(3)
        w.set_before(True)
        self.assertEqual(w.playhead_us, 270896)
        w.play_button.click()
        clock.ns = 126004000
        w._advance_playback()
        self.assertEqual(w.position, ui._Position(3, True))
        self.assertEqual(w.playhead_us, 396900)
        clock.ns = 126005000
        w._advance_playback()
        self.assertEqual(w.position, ui._Position(3))
        self.assertEqual(w.playhead_us, 396901)

    def test_time_slider_between_and_exact_completion_seeks(self):
        w = self.window
        self.time_mode()
        self.assertEqual((w.frame_slider.minimum(), w.frame_slider.maximum()), (0, 1305919))
        for time_us, frame in ((0, 0), (126004, 0), (126005, 1), (200123, 1), (270896, 2)):
            w.frame_slider.setValue(time_us)
            self.assertEqual(w.playhead_us, time_us)
            self.assertEqual(w.position.frame_index, frame)
            self.assertFalse(w.position.before)
        w.play_button.click()
        w.frame_slider.setValue(300123)
        self.assertFalse(w.play_timer.isActive())
        self.assertEqual(w.playhead_us, 300123)
        w.playback_mode.setCurrentText('Index')
        self.assertEqual((w.frame_slider.maximum(), w.frame_slider.value()), (9, 2))
        w.frame_slider.setValue(4)
        self.assertEqual(w.playhead_us, w.reconstruction.timeline.actions[3].cumulative_modeled_us)

    def test_time_slider_real_track_seek_and_handle_drag(self):
        w = self.window
        self.time_mode()
        slider = w.frame_slider
        slider.setPageStep(1)
        w.play_button.click()
        QTest.mouseClick(slider, Qt.LeftButton,
                         pos=QPoint(slider.width() * 4 // 5, slider.height() // 2))
        self.app.processEvents()
        self.assertFalse(w.play_timer.isActive())
        self.assertTrue(0.75 * slider.maximum() < w.playhead_us < 0.85 * slider.maximum())
        self.assertEqual(w.playhead_us, slider.value())
        self.assertEqual(w.position.frame_index, sum(a.cumulative_modeled_us <= w.playhead_us
                                                   for a in w.reconstruction.timeline.actions))
        option = QStyleOptionSlider()
        slider.initStyleOption(option)
        handle = slider.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, slider)
        QTest.mousePress(slider, Qt.LeftButton, pos=handle.center())
        self.assertTrue(slider.isSliderDown())
        target = QPoint(slider.width() // 3, handle.center().y())
        QApplication.sendEvent(slider, QMouseEvent(QEvent.MouseMove, QPointF(target),
            Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
        QTest.mouseRelease(slider, Qt.LeftButton, pos=target)
        self.app.processEvents()
        self.assertTrue(0.28 * slider.maximum() < w.playhead_us < 0.38 * slider.maximum())
        self.assertEqual(w.playhead_us, slider.value())

    def test_slider_overflow_fails_before_zini_and_fixed_reference_totals_fit(self):
        # Tracked reference constants only: no official sources, generation or replay.
        for ref in evidence_module._REFERENCES:
            for total in (ref.stage2_modeled_us, ref.stage3_modeled_us):
                self.assertLessEqual(total, 2**31 - 1)
        game = self.bundle.exemplars[0]
        oversized = replace(game.stage2, timeline=replace(game.stage2.timeline, total_modeled_us=2**31))
        bundle = replace(self.bundle, exemplars=(replace(game, stage2=oversized), *self.bundle.exemplars[1:]))
        with patch.object(ui, 'ZiniMetricJob') as job, self.assertRaisesRegex(ValueError, 'slider range'):
            ui.ExemplarBoardViewerWindow(bundle)
        job.assert_not_called()

    def test_invalid_time_seek_fails_without_changing_position(self):
        w = self.window
        self.time_mode()
        w.select_time(200123)
        for value in (-1, 1305920, True, 0.5, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                w.select_time(value)
            self.assertEqual((w.position, w.playhead_us), (ui._Position(1), 200123))

    def test_inactive_mode_switch_preserves_before_and_between_action_memory(self):
        w = self.window
        w.select_action(3)
        w.set_before(True)
        self.time_mode()
        self.assertEqual((w.position, w.playhead_us), (ui._Position(3, True), 270896))
        w.playback_mode.setCurrentText('Index')
        self.assertEqual(w.position, ui._Position(3, True))
        w.playback_mode.setCurrentText('Model C Time')
        w.select_time(300123)
        w.playback_mode.setCurrentText('Index')
        self.assertEqual(w.position, ui._Position(2))
        w.playback_mode.setCurrentText('Model C Time')
        self.assertEqual(w.playhead_us, 300123)
        self.assertFalse(w.play_timer.isActive())

    def test_active_mode_switch_continues_from_visible_completed_frame(self):
        w, clock = self.window, FakeWallClock()
        w._wall_clock = clock
        w.index_interval.setValue(375)
        w.select_frame(2)
        w.play_button.click()
        w.playback_mode.setCurrentText('Model C Time')
        self.assertTrue(w.play_timer.isActive())
        self.assertEqual(w.play_timer.interval(), 16)
        self.assertEqual((w.position.frame_index, w.playhead_us), (2, 270896))
        clock.ns = 30000000
        w._advance_playback()
        self.assertEqual(w.playhead_us, 300896)
        w.playback_mode.setCurrentText('Index')
        self.assertTrue(w.play_timer.isActive())
        self.assertEqual(w._index_interval_ms, 375)
        self.assertEqual(w.position, ui._Position(2))
        self.index_tick(w)
        self.assertEqual((w.position, w.playhead_us), (ui._Position(3), 396901))

    def test_all_eight_pair_playheads_restore_independently(self):
        w, clock = self.window, self.time_mode()
        expected = {}
        for offset, pair in enumerate(w._positions, 1):
            w.select_pair(*pair)
            time_us = w.reconstruction.timeline.actions[0].cumulative_modeled_us + offset
            w.select_time(time_us)
            w.play_button.click()
            clock.ns = 10000
            expected[pair] = time_us + 10
        w.play_button.click()  # Capture the final pair, too.
        for pair in reversed(expected):
            w.select_pair(*pair)
            self.assertEqual(w.playhead_us, expected[pair])
            self.assertEqual(w.position, ui._Position(1))
            self.assertEqual(w.frame_slider.value(), expected[pair])

    def test_active_solver_widget_switch_captures_old_pair_not_new_pair(self):
        w, clock = self.window, self.time_mode()
        job = w._zini_job
        starts, closes = len(job.starts), job.closes
        w.play_button.click()
        clock.ns = 200123000
        w.solver_selector.setCurrentIndex(1)
        self.assertFalse(w.play_timer.isActive())
        self.assertEqual(w.playhead_us, 0)
        w.select_time(210456)
        w.solver_selector.setCurrentIndex(0)
        self.assertEqual(w.playhead_us, 200123)
        w.solver_selector.setCurrentIndex(1)
        self.assertEqual(w.playhead_us, 210456)
        self.assertEqual((len(job.starts), job.closes), (starts, closes))

    def test_manual_navigation_aligns_model_time_to_resulting_frame(self):
        w, clock = self.window, self.time_mode()
        commands = (w.first_button.click, w.previous_button.click, w.next_button.click,
                    w.last_button.click, w.before_button.click,
                    lambda: QTest.keyClick(w.action_entry, Qt.Key_Return),
                    lambda: QTest.keyClick(w.action_entry, Qt.Key_Enter), w.action_go.click)
        for command in commands:
            w.select_action(3)
            w.play_button.click()
            clock.ns = 10000
            command()
            self.assertFalse(w.play_timer.isActive())
            k = w.position.frame_index
            self.assertEqual(w.playhead_us, w.reconstruction.timeline.actions[k - 1].cumulative_modeled_us if k else 0)
        w.select_action(3)
        w.set_before(True)
        w.play_button.click()
        w.after_button.click()
        self.assertEqual((w.position, w.playhead_us), (ui._Position(3), 396901))
        self.assertFalse(w.play_timer.isActive())

    def test_continuous_playhead_leaves_board_and_counter_authority_at_completed_frame(self):
        w, clock = self.window, self.time_mode()
        w.select_frame(1)
        w.play_button.click()
        with patch.object(w.board, 'present', wraps=w.board.present) as present:
            clock.ns = (200123 - 126005) * 1000
            w._advance_playback()
            present.assert_not_called()  # No unnecessary board repaint between completions.
        self.assertEqual(w.position, ui._Position(1))
        self.assertEqual(w.counter_values['Time (Model C)'].text(), '0.126')
        self.assertEqual(w.model_values['Cumulative Model C Time'].text(), '126005 us (0.126005 s)')
        self.assertEqual(w.playback_status.text(), 'Model C Time — 1x — 0.200123 / 1.305919 s')
        self.assertIn('last completed frame', w.playback_status.toolTip())

    def test_model_time_real_elapsed_timer_wiring(self):
        from PyQt5.QtCore import QElapsedTimer
        from PyQt5.QtTest import QSignalSpy
        w = self.window
        w._wall_clock = QElapsedTimer()
        self.assertIsInstance(w._wall_clock, QElapsedTimer)
        w.playback_mode.setCurrentText('Model C Time')
        spy = QSignalSpy(w.play_timer.timeout)
        w.play_button.click()
        self.assertTrue(spy.wait(1000))
        self.assertGreater(w.playhead_us, 0)
        w.play_button.click()
        paused = w.playhead_us
        QTest.qWait(30)
        self.assertEqual(w.playhead_us, paused)

    def test_synthetic_cursor_smoothstep_literal_oracles_and_exact_centers(self):
        overlay = self.window.board.targets
        for start, target in (((0, 0), (2, 1)), ((2, 1), (0, 0)), ((1, 1), (1, 1))):
            a, b = overlay.center(start), overlay.center(target)
            for u, q in ((0, 0), (0.25, 0.15625), (0.5, 0.5), (0.75, 0.84375), (1, 1)):
                with self.subTest(start=start, target=target, u=u):
                    self.assertEqual(overlay.interpolated_center(start, target, u), a + (b - a) * q)
        self.assertEqual(overlay.interpolated_center((0, 0), (2, 1), 0.25), QPointF(22.75, 18.375))
        self.assertNotEqual(overlay.interpolated_center((0, 0), (2, 1), 0.25), QPointF(28, 21))
        self.assertEqual(overlay.interpolated_center((0, 0), (2, 1), -1), QPointF(14, 14))
        self.assertEqual(overlay.interpolated_center((0, 0), (2, 1), 2), QPointF(70, 42))

    def test_static_cursor_initial_before_after_is_independent_of_preview(self):
        w, overlay = self.window, self.window.board.targets
        initial = w.reconstruction.timeline.evaluation.initial_cursor
        self.assertEqual(overlay.cursor_center, overlay.center(initial))
        self.assertEqual(len(w.findChildren(type(w.route_checkbox))), 2)  # No cursor checkbox.
        w.route_checkbox.setChecked(True)
        for ordinal in range(1, w.action_count + 1):
            w.select_action(ordinal)
            targets = tuple((a.event.x, a.event.y) for a in w.reconstruction.timeline.actions)
            self.assertEqual(overlay.cursor_center, overlay.center(targets[ordinal - 1]))
            w.set_before(True)
            self.assertEqual(overlay.cursor_center, overlay.center(targets[ordinal - 2] if ordinal > 1 else initial))
            self.assertEqual(overlay.current_target, targets[ordinal - 1])
            self.assertEqual(overlay.route_targets, targets[:ordinal - 1])
        self.assertIn('Not recorded mouse motion or an actual OS cursor trajectory', ui.CURSOR_NOTE)
        self.assertIn('Model C timing remains unchanged', ui.CURSOR_NOTE)
        self.assertTrue(any(ui.CURSOR_NOTE in label.toolTip() for label in w.findChildren(QLabel)))

    def test_model_time_cursor_partial_seek_and_exact_boundary_keep_prefix_authority(self):
        w = self.window
        self.time_mode()
        overlay = w.board.targets
        w.route_checkbox.setChecked(True)
        w.select_frame(1)
        counters, route = self.texts(w.counter_values), overlay.route_targets
        start = w.reconstruction.timeline.actions[0].cumulative_modeled_us
        end = w.reconstruction.timeline.actions[1].cumulative_modeled_us
        elapsed = (end - start) // 4
        w.select_time(start + elapsed)
        self.assertEqual(w.position.frame_index, 1)
        self.assertEqual(self.texts(w.counter_values), counters)
        self.assertEqual(overlay.route_targets, route)
        self.assertEqual(overlay.cursor_center,
                         overlay.interpolated_center((0, 0), (1, 1), Fraction(elapsed, end - start)))
        w.select_time(end)
        self.assertEqual(w.position, ui._Position(2))
        self.assertEqual(overlay.route_targets, ((0, 0), (1, 1)))
        self.assertEqual(overlay.cursor_center, QPointF(42, 42))
        w.select_pair(10, 'stage3')
        actions = w.reconstruction.timeline.actions
        w.select_time(actions[3].cumulative_modeled_us + actions[4].modeled_action_us // 2)
        self.assertEqual(overlay.cursor_center, overlay.center((2, 0)))  # Same-target pending CHORD.

    def test_model_time_cursor_pause_resume_and_speed_reanchor_no_jump(self):
        w, clock = self.window, self.time_mode()
        w.select_frame(1)
        w.play_button.click()
        clock.ns = 36000000
        w.play_button.click()  # Pause samples even without a refresh.
        point, playhead = QPointF(w.board.targets.cursor_center), w.playhead_us
        self.assertEqual(playhead, 162005)
        self.assertNotEqual(point, QPointF(14, 14))
        clock.ns = 10**15
        w._advance_playback()
        self.assertEqual(w.board.targets.cursor_center, point)
        w.play_button.click()
        self.assertEqual(w.playhead_us, playhead)
        self.assertEqual(w.board.targets.cursor_center, point)
        clock.ns = 10000000
        w._advance_playback()
        point, playhead = QPointF(w.board.targets.cursor_center), w.playhead_us
        w.playback_speed.setValue(2)
        self.assertEqual(w.playhead_us, playhead)
        self.assertEqual(w.board.targets.cursor_center, point)
        clock.ns = 1000000
        w._advance_playback()
        self.assertEqual(w.playhead_us, playhead + 2000)
        self.assertNotEqual(w.board.targets.cursor_center, point)

    def test_model_cursor_catchup_refreshes_board_once_then_interpolates_pending_segment(self):
        w, clock = self.window, self.time_mode()
        w.route_checkbox.setChecked(True)
        actions = w.reconstruction.timeline.actions
        elapsed = actions[5].modeled_action_us // 4
        w.play_button.click()
        clock.ns = (actions[4].cumulative_modeled_us + elapsed) * 1000
        with patch.object(w.board, 'present', wraps=w.board.present) as present:
            w._advance_playback()
            present.assert_called_once()
        self.assertEqual(w.position, ui._Position(5))
        self.assert_route_prefix()
        start, end = ((a.event.x, a.event.y) for a in actions[4:6])
        self.assertEqual(w.board.targets.cursor_center,
                         w.board.targets.interpolated_center(start, end, Fraction(elapsed, actions[5].modeled_action_us)))

    def test_index_cursor_slow_interval_smoothstep_and_no_premature_commit(self):
        w, clock = self.window, self.window._wall_clock
        w.index_interval.setValue(1000)
        w.select_action(2)
        w.set_before(True)
        w.route_checkbox.setChecked(True)
        counters = self.texts(w.counter_values)
        w.play_button.click()
        for elapsed, point in ((0, QPointF(14, 14)), (250, QPointF(18.375, 18.375)),
                               (500, QPointF(28, 28)), (750, QPointF(37.625, 37.625))):
            clock.ns = elapsed * 1_000_000
            w._advance_playback()
            self.assertEqual(w.position, ui._Position(2, True))
            self.assertEqual(w.board.targets.cursor_center, point)
            self.assertEqual(w.board.targets.route_targets, ((0, 0),))
            self.assertEqual(self.texts(w.counter_values), counters)
        clock.ns = 1_000_000_000
        w._advance_playback()
        self.assertEqual(w.position, ui._Position(2))
        self.assertEqual(w.board.targets.cursor_center, QPointF(42, 42))
        self.assertEqual(len(w.board.targets.route_targets), 2)

    def test_index_pause_resume_preserves_partial_and_manual_navigation_discards_it(self):
        w, clock = self.window, self.window._wall_clock
        w.index_interval.setValue(1000)
        w.select_frame(1)
        w.play_button.click()
        clock.ns = 250000000
        w.play_button.click()
        point = QPointF(w.board.targets.cursor_center)
        self.assertEqual(w._index_partial, Fraction(1, 4))
        self.assertEqual(point, QPointF(18.375, 18.375))
        w.play_button.click()
        self.assertEqual(w.board.targets.cursor_center, point)
        clock.ns = 500000000
        w._advance_playback()
        self.assertEqual(w._index_partial, Fraction(3, 4))
        self.assertEqual(w.board.targets.cursor_center, QPointF(37.625, 37.625))
        clock.ns = 750000000
        w._advance_playback()
        self.assertEqual(w.position, ui._Position(2))
        for index, command in enumerate((w.first_button.click, w.previous_button.click, w.next_button.click,
                                        w.last_button.click, w.before_button.click, w.after_button.click,
                                        w.action_go.click, lambda: w.frame_slider.setValue(0))):
            w.select_action(2)
            w.set_before(index != 4)  # Exercise Before from AFTER; otherwise it is disabled.
            w.play_button.click()
            clock.ns = 250000000
            w._advance_playback()
            command()
            self.assertFalse(w.play_timer.isActive())
            self.assertEqual(w._index_partial, 0)
            k = w.position.frame_index
            targets = w._targets[w.pair]
            self.assertEqual(w.board.targets.cursor_center,
                             w.board.targets.center(targets[k - 1] if k else (0, 0)))

    def test_index_interval_change_preserves_fraction_and_uses_new_remaining_duration(self):
        w, clock = self.window, self.window._wall_clock
        w.index_interval.setValue(1000)
        w.select_frame(1)
        w.play_button.click()
        clock.ns = 250000000
        w.index_interval.setValue(2000)
        self.assertEqual(w.position, ui._Position(1))
        self.assertEqual(w._index_partial, Fraction(1, 4))
        self.assertEqual(w.board.targets.cursor_center, QPointF(18.375, 18.375))
        self.assertEqual(clock.ns, 0)
        clock.ns = 1_000_000_000
        w._advance_playback()
        self.assertEqual(w._index_partial, Fraction(3, 4))
        self.assertEqual(w.position, ui._Position(1))
        clock.ns = 1_500_000_000
        w._advance_playback()
        self.assertEqual(w.position, ui._Position(2))
        self.assertEqual(w._index_partial, 0)
        w.play_button.click()
        w.index_interval.setValue(20)
        w.play_button.click()
        clock.ns = 19_999_999
        w._advance_playback()
        self.assertEqual(w.position, ui._Position(2))
        clock.ns = 20_000_000
        w._advance_playback()
        self.assertEqual(w.position, ui._Position(3))

    def test_index_late_refresh_catches_up_without_duplicate_actions(self):
        w, clock = self.window, self.window._wall_clock
        w.index_interval.setValue(1000)
        w.select_frame(1)
        w.play_button.click()
        clock.ns = 3_250_000_000
        with patch.object(w.board, 'present', wraps=w.board.present) as present:
            w._advance_playback()
            present.assert_called_once()
        self.assertEqual(w.position, ui._Position(4))
        self.assertEqual(w._index_partial, Fraction(1, 4))
        self.assertEqual(w.board.targets.cursor_center, QPointF(22.75, 37.625))
        point = QPointF(w.board.targets.cursor_center)
        w._advance_playback()  # Same wall sample must not count another action.
        self.assertEqual(w.position, ui._Position(4))
        self.assertEqual(w.board.targets.cursor_center, point)
        clock.ns = 100_000_000_000
        w._advance_playback()
        self.assertFalse(w.play_timer.isActive())
        self.assertEqual(w.position.frame_index, w.action_count)

    def test_smooth_mode_switch_discards_index_partial_and_preserves_existing_mode_contract(self):
        w, clock = self.window, self.window._wall_clock
        w.index_interval.setValue(1000)
        w.select_frame(1)
        w.play_button.click()
        clock.ns = 250000000
        w._advance_playback()
        self.assertNotEqual(w.board.targets.cursor_center, QPointF(14, 14))
        w.playback_mode.setCurrentText('Model C Time')
        self.assertTrue(w.play_timer.isActive())
        self.assertEqual(w.playhead_us, 126005)
        self.assertEqual(w._index_partial, 0)
        self.assertEqual(w.board.targets.cursor_center, QPointF(14, 14))
        clock.ns = 36000000
        w._advance_playback()
        point, playhead = QPointF(w.board.targets.cursor_center), w.playhead_us
        w.playback_mode.setCurrentText('Index')
        self.assertEqual(w.position, ui._Position(1))
        self.assertEqual(w.board.targets.cursor_center, QPointF(14, 14))
        self.assertEqual(w._index_partial, 0)
        self.assertTrue(w.play_timer.isActive())
        w.playback_mode.setCurrentText('Model C Time')
        self.assertEqual(w.playhead_us, playhead)  # Existing modeled playhead memory.
        self.assertEqual(w.board.targets.cursor_center, point)

    def test_partial_cursor_refresh_in_both_modes_touches_no_cells_counters_or_zini(self):
        w, clock = self.window, self.window._wall_clock
        for mode in ('Index', 'Model C Time'):
            w.playback_mode.setCurrentText(mode)
            w.index_interval.setValue(1000)
            w.select_frame(1)
            w.play_button.click()
            counters = self.texts(w.counter_values)
            route = w.board.targets.route_targets
            point = QPointF(w.board.targets.cursor_center)
            with patch.object(w.board, 'present', side_effect=AssertionError('Board redraw')), \
                 patch.object(ui.ExemplarViewerCell, 'render_state', side_effect=AssertionError('Cell render')), \
                 patch.object(w, '_refresh', side_effect=AssertionError('Full refresh')), \
                 patch.object(w._zini_job, 'start', side_effect=AssertionError('ZiNi start')), \
                 patch.object(w._zini_job, 'close', side_effect=AssertionError('ZiNi cancel')):
                for elapsed in (10000000, 20000000, 30000000):
                    clock.ns = elapsed
                    w._advance_playback()
                w.play_button.click()  # Pause/resume without a boundary is also partial refresh only.
                w.play_button.click()
            self.assertNotEqual(w.board.targets.cursor_center, point)
            self.assertEqual(w.position, ui._Position(1))
            self.assertEqual(self.texts(w.counter_values), counters)
            self.assertEqual(w.board.targets.route_targets, route)
            w.play_button.click()

    def test_interval_max_and_upper_label_fit_native_edit_rect_at_changed_font_size(self):
        entry = self.window.index_interval
        original = entry.font()
        for extra in (0, 4):
            font = entry.font()
            font.setPointSize(max(8, original.pointSize()) + extra)
            entry.setFont(font)
            self.app.processEvents()
            for value, text in ((20, 'Max (20 ms)'), (5000, '5000 ms')):
                entry.setValue(value)
                option = QStyleOptionSpinBox()
                entry.initStyleOption(option)
                edit = entry.style().subControlRect(QStyle.CC_SpinBox, option, QStyle.SC_SpinBoxEditField, entry)
                self.assertEqual(entry.text(), text)
                self.assertGreaterEqual(edit.width(), entry.fontMetrics().horizontalAdvance(text) +
                                        entry.fontMetrics().horizontalAdvance(' '))
                up = entry.style().subControlRect(QStyle.CC_SpinBox, option, QStyle.SC_SpinBoxUp, entry)
                self.assertFalse(edit.intersects(up))

    def test_route_contrast_and_cursor_layer_above_history_and_selected_context(self):
        overlay = self.window.board.targets
        self.assertEqual(overlay.ROUTE_COLOR.alpha(), 165)
        self.assertGreaterEqual(overlay.ROUTE_WIDTH, 2)
        self.window.select_action(3)
        self.window.route_checkbox.setChecked(True)
        painter = MagicMock()
        with patch.object(ui, 'QPainter', return_value=painter):
            overlay.paintEvent(None)
        operations = [call[0] for call in painter.method_calls]
        self.assertLess(operations.index('drawPolyline'), operations.index('drawLine'))
        self.assertLess(operations.index('drawRect'), len(operations) - 1)
        self.assertEqual(operations[-1], 'drawEllipse')
        self.assertEqual(painter.drawEllipse.call_args.args, (overlay.cursor_center, 9, 9))
        self.assertTrue(overlay.testAttribute(Qt.WA_TransparentForMouseEvents))

    def test_partial_cursor_invalidates_only_old_and_new_marker_rectangles(self):
        w, clock = self.window, self.window._wall_clock
        w.index_interval.setValue(1000)
        w.select_frame(1)
        w.play_button.click()
        with patch.object(w.board.targets, 'update', wraps=w.board.targets.update) as redraw:
            clock.ns = 250000000
            w._advance_playback()
            self.assertEqual(redraw.call_count, 2)
            for call in redraw.call_args_list:
                self.assertEqual(len(call.args), 1)
                self.assertLessEqual(call.args[0].width(), 25)
                self.assertLessEqual(call.args[0].height(), 25)

    def test_initial_action_entry_focus_loss_by_click_preserves_initial(self):
        w = self.window
        position = w.position
        self.focus_entry(w.action_entry)
        self.click_answer_checkbox()
        self.assertEqual(w.position, position)
        self.assertIsNone(w.position.action_ordinal)
        self.assertEqual(w.position.frame_index, 0)

    def test_before_action_entry_focus_loss_preserves_selected_action_and_side(self):
        w = self.window
        w.select_action(3)
        w.set_before(True)
        position = w.position
        self.focus_entry(w.action_entry)
        self.click_answer_checkbox()
        self.assertEqual(w.position, position)
        self.assertEqual((w.position.action_ordinal, w.position.before, w.position.frame_index), (3, True, 2))

    def test_initial_action_entry_tab_away_preserves_initial(self):
        w = self.window
        position = w.position
        self.focus_entry(w.action_entry)
        QTest.keyClick(w.action_entry, Qt.Key_Tab)
        self.app.processEvents()
        self.assertFalse(w.action_entry.hasFocus() or w.action_entry.lineEdit().hasFocus())
        self.assertEqual(w.position, position)

    def test_action_entry_return_and_enter_interpret_text_and_commit_once(self):
        w = self.window
        for key in (Qt.Key_Return, Qt.Key_Enter):
            with self.subTest(key=key):
                w.select_frame(0)
                self.type_entry(w.action_entry, '3')
                self.assertFalse(w.action_entry.keyboardTracking())
                self.assertEqual(w.action_entry.value(), 1)
                self.assertIsNone(w.position.action_ordinal)
                with patch.object(w, 'select_action', wraps=w.select_action) as select:
                    QTest.keyClick(w.action_entry.lineEdit(), key)
                    self.app.processEvents()
                select.assert_called_once_with(3)
                self.assertEqual((w.position.action_ordinal, w.position.before), (3, False))

    def test_uncommitted_edited_text_focus_loss_does_not_navigate(self):
        w = self.window
        position = w.position
        self.type_entry(w.action_entry, '3')
        self.click_answer_checkbox()
        self.assertEqual(w.position, position)

    def test_navigation_button_after_entry_focus_loss_navigates_only_once(self):
        w = self.window
        self.focus_entry(w.action_entry)
        with patch.object(w, 'select_frame', wraps=w.select_frame) as select:
            QTest.mouseClick(w.next_button, Qt.LeftButton)
            self.app.processEvents()
        select.assert_called_once_with(1)
        self.assertEqual((w.position.action_ordinal, w.position.before), (1, False))

    def test_before_after_labels_and_frame_navigation_semantics(self):
        w = self.window
        w.select_action(3)
        w.before_button.click()
        self.assertEqual((w.position.action_ordinal, w.position.frame_index), (3, 2))
        self.assertIn('Displayed frame 2 / 9', w.frame_label.text())
        self.assertIn('Selected action 3 / 9', w.action_label.text())
        self.assertIn('not yet applied', w.inspection_label.text())
        self.assertFalse(w.before_button.isEnabled())
        self.assertTrue(w.after_button.isEnabled())
        w.after_button.click()
        self.assertEqual(w.position.frame_index, 3)
        w.before_button.click()
        w.previous_button.click()
        self.assertEqual((w.position.action_ordinal, w.position.before), (1, False))
        w.select_action(3)
        w.before_button.click()
        w.next_button.click()
        self.assertEqual((w.position.action_ordinal, w.position.before), (3, False))

    def test_before_first_is_distinct_from_initial_and_first_restores_initial(self):
        w = self.window
        w.select_action(1)
        w.set_before(True)
        self.assertEqual(w.position.frame_index, 0)
        self.assertIn('Selected recorded action 1 — not yet applied', w.inspection_label.text())
        self.assertEqual(w.action_values['Action type'].text(), 'OPEN')
        self.assertTrue(w.first_button.isEnabled())
        self.assertFalse(w.previous_button.isEnabled())
        w.first_button.click()
        self.assertIsNone(w.position.action_ordinal)
        self.assertEqual(w.action_values['Action type'].text(), 'unavailable')
        w.select_action(1)
        w.set_before(True)
        w.select_frame(0)  # Explicit frame 0 (slider authority) resets BEFORE 1.
        self.assertIsNone(w.position.action_ordinal)

    def test_invalid_nonwidget_inputs_fail_without_changing_position(self):
        w = self.window
        for method, values in ((w.select_frame, (-1, 10, True, 1.0, '1', None)),
                               (w.select_action, (0, 10, False, 1.0, '1', None)),
                               (w.set_before, (0, 1, 'before', None))):
            for value in values:
                with self.subTest(method=method.__name__, value=value), self.assertRaises(ValueError):
                    method(value)
        for pair in ((True, 'stage2'), (999, 'stage2'), (10, 'other'), ('10', 'stage2')):
            with self.assertRaises(ValueError):
                w.select_pair(*pair)
        self.assertIsNone(w.position.action_ordinal)

    def test_every_stored_frame_is_rendered_by_lookup(self):
        for game in self.bundle.exemplars:
            for solver in ('stage2', 'stage3'):
                self.window.select_pair(game.reference.game_index, solver)
                for k in range(self.window.action_count + 1):
                    self.window.select_frame(k)
                    self.assert_frame()

    def test_loss_terminal_feedback_and_before_terminal(self):
        w = self.window
        w.select_pair(20, 'stage3')
        w.last_button.click()
        states = {cell.logical_state for cell in w.board.cells.values()}
        self.assertTrue({CellState.EXPLODED, CellState.MINE, CellState.FALSE_FLAG, CellState.FLAGGED} <= states)
        self.assertIn('Terminal Engine feedback', w.status_label.text())
        self.assertEqual(w.reference_values['Final recorded outcome'].text(), 'LOSS')
        w.before_button.click()
        self.assertNotIn('Terminal Engine feedback', w.status_label.text())
        self.assertIn('PLAYING', w.status_label.text())
        self.assertEqual(w.board.cells[1, 0].logical_state, CellState.HIDDEN)
        self.assertEqual(w.reference_values['Final recorded outcome'].text(), 'LOSS')

    def test_automatic_win_flags_are_public_effects_not_extra_actions(self):
        w = self.window
        w.select_pair(40, 'stage3')
        w.last_button.click()
        self.assertEqual(w.board.cells[1, 1].logical_state, CellState.FLAGGED)
        self.assertEqual(w.action_values['Explicit flag delta'].text(), '0')
        self.assertEqual(w.position.frame_index, 8)

    def test_overlay_default_off_and_hidden_only_answers_include_blank_zero(self):
        w = self.window
        self.assertFalse(w.answer_checkbox.isChecked())
        self.assertTrue(all(not cell.answer_layer.glyph for cell in w.board.cells.values()))
        w.answer_checkbox.setChecked(True)
        self.assertEqual(w.board.cells[1, 1].answer_layer.glyph, '✹')
        self.assertEqual(w.board.cells[0, 0].answer_layer.glyph, '1')
        self.assertAlmostEqual(w.board.cells[0, 0].answer_layer.graphicsEffect().opacity(), 0.35)
        w.select_pair(30, 'stage2')
        self.assertEqual(w.board.cells[3, 2].answer_layer.glyph, '')
        self.assertEqual(w.board.cells[3, 2].logical_state, CellState.HIDDEN)

    def test_overlay_off_restores_exact_public_representation_and_pixels(self):
        w = self.window
        cell = w.board.cells[1, 1]
        before = self.cell_state(cell)
        image = cell.grab().toImage()
        w.answer_checkbox.setChecked(True)
        self.app.processEvents()
        self.assertEqual(cell.text(), '')
        self.assertEqual(cell.styleSheet(), before[2])
        self.assertNotEqual(cell.grab().toImage(), image)
        w.answer_checkbox.setChecked(False)
        self.app.processEvents()
        self.assertEqual(self.cell_state(cell), before)
        self.assertEqual(cell.grab().toImage(), image)

    def test_overlay_never_changes_nonhidden_cells_or_metadata(self):
        w = self.window
        for game, solver, frame in ((10, 'stage3', 3), (20, 'stage2', 4), (40, 'stage3', 8)):
            w.select_pair(game, solver)
            w.select_frame(frame)
            before = {xy: self.cell_state(cell) for xy, cell in w.board.cells.items()
                      if cell.logical_state != CellState.HIDDEN}
            context, position = self.texts(w.action_values), w.position
            observation = w.reconstruction.frames[frame].observation
            w.answer_checkbox.setChecked(True)
            for xy, state in before.items():
                self.assertEqual(self.cell_state(w.board.cells[xy]), state)
            self.assertEqual(self.texts(w.action_values), context)
            self.assertEqual(w.position, position)
            self.assertIs(w.reconstruction.frames[frame].observation, observation)
            w.answer_checkbox.setChecked(False)

    def test_hidden_answers_never_enter_tooltip_or_accessibility_text(self):
        w = self.window
        before = {xy: (cell.toolTip(), cell.accessibleName(), cell.accessibleDescription())
                  for xy, cell in w.board.cells.items()}
        w.answer_checkbox.setChecked(True)
        for xy, cell in w.board.cells.items():
            self.assertEqual((cell.toolTip(), cell.accessibleName(), cell.accessibleDescription()), before[xy])
            self.assertEqual(cell.answer_layer.toolTip(), '')
            self.assertEqual(cell.answer_layer.accessibleName(), '')
            self.assertEqual(cell.answer_layer.accessibleDescription(), '')
            self.assertFalse(cell.answer_layer.findChildren(QLabel))
            self.assertNotIsInstance(cell.answer_layer, QLabel)

    def test_revealed_palette_supports_all_numbers_and_zero(self):
        cell = self.window.board.cells[0, 0]
        for value in range(9):
            cell.render_state(value, answer=-1)
            self.assertEqual(cell.text(), str(value) if value else '')
            self.assertEqual(cell.answer_layer.glyph, '')
            self.assertIn(ui.NUMBER_COLORS.get(value, '#000000'), cell.styleSheet())

    def test_new_safe_highlight_only_after_and_exact_coordinates(self):
        w = self.window
        w.select_pair(10, 'stage3')
        w.select_action(3)
        expected = w.reconstruction.newly_revealed_safe_by_action[2]
        self.assertEqual({xy for xy, cell in w.board.cells.items() if cell.newly_safe}, expected)
        w.set_before(True)
        self.assertFalse(any(cell.newly_safe for cell in w.board.cells.values()))
        self.assertEqual(w.action_values['Reconstructed new-safe count'].text(), str(len(expected)))
        w.select_frame(0)
        self.assertFalse(any(cell.newly_safe for cell in w.board.cells.values()))
        w.select_pair(20, 'stage3')
        w.last_button.click()
        self.assertFalse(any(cell.newly_safe for cell in w.board.cells.values()))

    def test_first_action_has_no_previous_target_or_origin_line(self):
        w = self.window
        w.select_action(1)
        self.assertEqual(w.board.targets.current_target, (0, 0))
        self.assertIsNone(w.board.targets.previous_target)
        self.assertIsNone(w.board.targets.transition_line)
        self.assertEqual(w.action_values['Previous recorded target'].text(), 'unavailable')
        self.assertEqual(w.model_values['Initial Model C cursor'].text(), '(0, 0)')

    def test_target_geometry_same_target_and_before_after_independence(self):
        w = self.window
        w.select_pair(10, 'stage3')
        w.select_action(2)
        self.assertEqual(w.board.targets.transition_line, ((0, 0), (1, 1)))
        self.assertEqual([w.action_values[name].text() for name in ('dx', 'dy', 'd²')], ['1', '1', '2'])
        w.set_before(True)
        self.assertEqual(w.board.targets.transition_line, ((0, 0), (1, 1)))
        w.select_action(5)
        self.assertEqual(w.board.targets.current_target, (2, 0))
        self.assertEqual(w.board.targets.previous_target, (2, 0))
        self.assertIsNone(w.board.targets.transition_line)
        self.assertEqual([w.action_values[name].text() for name in ('dx', 'dy', 'd²')], ['0', '0', '0'])
        self.assertGreater(int(w.action_values['Selected Model C action us'].text()), 0)

    def assert_route_prefix(self):
        w = self.window
        expected = tuple((item.event.x, item.event.y)
                         for item in w.reconstruction.timeline.actions[:w.position.frame_index])
        self.assertEqual(w.board.targets.route_targets, expected)
        self.assertIsInstance(w.board.targets.route_targets, tuple)

    def test_route_default_off_and_selected_transition_remains(self):
        w = self.window
        self.assertEqual(w.route_checkbox.text(), 'Show action-target route')
        self.assertFalse(w.route_checkbox.isChecked())
        self.assertFalse(w.board.targets.show_route)
        self.assertEqual(ui.ROUTE_NOTE, 'Action-target route — not recorded cursor trajectory')
        self.assertIn(ui.ROUTE_NOTE, w.route_checkbox.toolTip())
        self.assertTrue(w.board.targets.testAttribute(Qt.WA_TransparentForMouseEvents))
        w.select_action(2)
        self.assertFalse(w.board.targets.show_route)
        self.assertEqual(w.board.targets.transition_line, ((0, 0), (1, 1)))
        self.assertEqual(w.board.targets.current_target, (1, 1))
        self.assertEqual(w.board.targets.previous_target, (0, 0))

    def test_route_initial_first_second_and_before_after_completed_prefixes(self):
        w = self.window
        w.route_checkbox.setChecked(True)
        self.assertEqual(w.board.targets.route_targets, ())
        w.select_action(1)
        self.assertEqual(w.board.targets.route_targets, ((0, 0),))
        self.assertIsNone(w.board.targets.transition_line)
        w.select_action(2)
        self.assertEqual(w.board.targets.route_targets, ((0, 0), (1, 1)))
        for ordinal in range(1, w.action_count + 1):
            w.select_action(ordinal)
            self.assert_route_prefix()
            self.assertEqual(len(w.board.targets.route_targets), ordinal)
            w.set_before(True)
            self.assert_route_prefix()
            self.assertEqual(len(w.board.targets.route_targets), ordinal - 1)
            # Inspection target remains available but is absent from route membership.
            event = w.reconstruction.timeline.actions[ordinal - 1].event
            self.assertEqual(w.board.targets.current_target, (event.x, event.y))
            w.set_before(False)
            self.assert_route_prefix()

    def test_route_all_navigation_and_pair_memory_use_only_completed_targets(self):
        w = self.window
        w.route_checkbox.setChecked(True)
        expected = {}
        for pair in w._positions:
            w.select_pair(*pair)
            w.last_button.click()
            self.assert_route_prefix()
            self.assertEqual(len(w.board.targets.route_targets), w.action_count)
            for command in (w.previous_button.click, w.first_button.click, w.next_button.click,
                            lambda: w.frame_slider.setValue(2)):
                command()
                self.assert_route_prefix()
            w.action_entry.setValue(3)
            w.action_go.click()
            self.assert_route_prefix()
            w.set_before(True)
            expected[pair] = w.board.targets.route_targets
            self.assert_route_prefix()
        for pair in reversed(expected):
            w.select_pair(*pair)
            self.assertEqual(w.board.targets.route_targets, expected[pair])
            self.assert_route_prefix()

    def test_route_index_autoplay_adds_exactly_one_completed_target_per_tick(self):
        w = self.window
        w.route_checkbox.setChecked(True)
        w.play_button.click()
        for ordinal in range(1, w.action_count + 1):
            self.index_tick(w)
            self.assertEqual(len(w.board.targets.route_targets), ordinal)
            self.assert_route_prefix()

    def test_route_model_time_seek_and_autoplay_exclude_future_target(self):
        w, clock = self.window, self.time_mode()
        w.route_checkbox.setChecked(True)
        w.frame_slider.setValue(200123)
        self.assertEqual(w.board.targets.route_targets, ((0, 0),))
        w.frame_slider.setValue(270896)
        self.assertEqual(w.board.targets.route_targets, ((0, 0), (1, 1)))
        w.select_action(3)
        w.set_before(True)
        w.play_button.click()
        clock.ns = 126004000
        w._advance_playback()
        self.assertEqual(w.position, ui._Position(3, True))
        self.assertEqual(len(w.board.targets.route_targets), 2)
        clock.ns += 1000
        w._advance_playback()
        self.assertEqual(len(w.board.targets.route_targets), 3)
        self.assert_route_prefix()
        clock.ns = 10**15
        w._advance_playback()
        self.assertEqual(len(w.board.targets.route_targets), w.action_count)
        self.assert_route_prefix()

    def test_route_same_target_actions_keep_repeated_point_without_detour(self):
        w = self.window
        w.select_pair(10, 'stage3')
        w.route_checkbox.setChecked(True)
        w.select_action(5)
        self.assertEqual(w.board.targets.route_targets, ((0, 0), (1, 1), (0, 0), (2, 0), (2, 0)))
        self.assertIsNone(w.board.targets.transition_line)

    def test_route_toggle_preserves_active_playback_playhead_and_zini_in_both_modes(self):
        w = self.window
        clock = FakeWallClock()
        w._wall_clock = clock
        for mode in ('Index', 'Model C Time'):
            w.playback_mode.setCurrentText(mode)
            w.select_action(3)
            w.play_button.click()
            clock.ns = 10000000
            state = (w.position, w.playhead_us, w._anchor_model_us, clock.ns)
            with patch.object(w._zini_job, 'start', side_effect=AssertionError('ZiNi start')), \
                 patch.object(w._zini_job, 'close', side_effect=AssertionError('ZiNi cancel')), \
                 patch.object(w.play_timer, 'start', side_effect=AssertionError('timer restart')), \
                 patch.object(w.play_timer, 'stop', side_effect=AssertionError('timer stop')):
                for show in (True, False, True):
                    w.route_checkbox.setChecked(show)
                    self.assertEqual(w.board.targets.show_route, show)
                    self.assertEqual((w.position, w.playhead_us, w._anchor_model_us, clock.ns), state)
                    self.assertTrue(w.play_timer.isActive())
            w.play_button.click()

    def test_route_and_answer_layers_are_independent_and_public_text_unchanged(self):
        w = self.window
        w.select_action(3)
        for answers in (False, True):
            w.answer_checkbox.setChecked(answers)
            public = {xy: self.cell_state(cell) for xy, cell in w.board.cells.items()}
            for route in (True, False):
                w.route_checkbox.setChecked(route)
                self.assertEqual(w.answer_checkbox.isChecked(), answers)
                self.assertEqual({xy: self.cell_state(cell) for xy, cell in w.board.cells.items()}, public)
                self.assertEqual(w.board.targets.show_route, route)
        w.route_checkbox.setChecked(True)
        w.answer_checkbox.setChecked(True)
        self.assertTrue(w.board.targets.show_route)
        w.answer_checkbox.setChecked(False)
        self.assertTrue(w.board.targets.show_route)

    def test_route_pixels_change_for_history_and_off_restores_board_exactly(self):
        w = self.window
        w.last_button.click()
        self.app.processEvents()
        image = w.board.grab().toImage()
        w.route_checkbox.setChecked(True)
        self.app.processEvents()
        self.assertNotEqual(w.board.grab().toImage(), image)
        w.route_checkbox.setChecked(False)
        self.app.processEvents()
        self.assertEqual(w.board.grab().toImage(), image)
        # Initial and single-target frames have no historical segment to paint.
        for index in (0, 1):
            w.select_frame(index)
            image = w.board.grab().toImage()
            w.route_checkbox.setChecked(True)
            self.assertEqual(w.board.grab().toImage(), image)
            w.route_checkbox.setChecked(False)

    def test_reference_panel_and_solver_policy_are_factual_and_plain_text(self):
        w = self.window
        game = self.bundle.exemplars[0]
        self.assertEqual(w.reference_values['Accepted category'].text(), game.reference.category)
        self.assertEqual(w.reference_values['Accepted category'].textFormat(), Qt.PlainText)
        self.assertIn('OPEN / FLAG only', w.policy_note.text())
        for name, value in (('Total 3BV', game.stage2.board_reference.total_3bv),
                            ('Total Ops', game.stage2.board_reference.total_ops),
                            ('Isolated-number count', game.stage2.board_reference.isolated_number_count)):
            self.assertEqual(w.reference_values[name].text(), str(value))
        w.select_pair(10, 'stage3')
        self.assertIn('OPEN / FLAG / CHORD', w.policy_note.text())

    def test_counter_rows_order_final_strings_and_explicit_modeled_time(self):
        w = self.window
        self.assertEqual(tuple(w.counter_values), ('Time (Model C)','Est Time (Model C)','3BV','3BV/s (Model C)','Clicks','Left','Right',
            'Chord','CPS (Model C)','Efficiency','IOE','Ops','Thrp','Corr','ZiNi','ZNE','ZNT'))
        for game in self.bundle.exemplars:
            w.select_pair(game.reference.game_index, 'stage3')
            final = w.reconstruction.final_counters
            initial = self.texts(w.counter_values)
            self.assertEqual(initial['Clicks'], '0')
            self.assertEqual(initial['3BV'], f'0/{w.reconstruction.board_reference.total_3bv}')
            self.assertEqual(initial['Ops'], f'0/{w.reconstruction.board_reference.total_ops}')
            w.last_button.click()
            for label, field in (('3BV','bbbv_text'),('Ops','ops_text'),('Clicks','clicks_text'),
                                  ('Left','left_text'),('Right','right_text'),('Chord','chord_text')):
                self.assertEqual(w.counter_values[label].text(), getattr(final, field))
            self.assertNotEqual(w.counter_values['Time (Model C)'].text(), '-')
            self.assertIn('Model C', w.counter_values['Time (Model C)'].toolTip())
            terminal = self.texts(w.counter_values)
            w.answer_checkbox.setChecked(True)
            self.assertEqual(self.texts(w.counter_values), terminal)
            w.first_button.click()
            self.assertEqual(self.texts(w.counter_values), initial)

    def test_counters_follow_each_displayed_frame_including_before(self):
        w = self.window
        for pair in w._positions:
            w.select_pair(*pair)
            for ordinal in range(1, w.action_count + 1):
                w.select_action(ordinal)
                for before in (True, False):
                    w.set_before(before)
                    current = w.reconstruction.frame_counters[ordinal - int(before)]
                    ref = w.reconstruction.board_reference
                    for label, field in (('Clicks', 'clicks_text'), ('Left', 'left_text'),
                                          ('Right', 'right_text'), ('Chord', 'chord_text')):
                        self.assertEqual(w.counter_values[label].text(), getattr(current, field))
                    self.assertEqual(w.counter_values['3BV'].text(), f'{current.completed_3bv}/{ref.total_3bv}')
                    self.assertEqual(w.counter_values['Ops'].text(), f'{current.completed_ops}/{ref.total_ops}')
                    for label in ('ZiNi', 'ZNE', 'ZNT'):
                        self.assertEqual(w.counter_values[label].text(), '-')

    def test_counter_ratios_rounding_and_zero_denominators(self):
        original_game = self.bundle.exemplars[0]
        cases = (
            (3, 4, 2, ('29%', '0.2857', '0.6667', '0.4286')),
            (4, 4, 1, ('12%', '0.1250', '0.2500', '0.5000')),
            (0, 0, 0, ('-', '-', '-', '-')),
            (0, 2, 1, ('50%', '0.5000', '-', '0.0000')),
        )
        for active, wasted, b, expected in cases:
            current = replace(original_game.stage2.frame_counters[0], active_clicks=active,
                            wasted_clicks=wasted, completed_3bv=b)
            game = replace(original_game, stage2=replace(original_game.stage2,
                frame_counters=(current, *original_game.stage2.frame_counters[1:])))
            w = ui.ExemplarBoardViewerWindow(replace(self.bundle, exemplars=(game, *self.bundle.exemplars[1:])))
            try:
                for name, value in zip(('Efficiency', 'IOE', 'Thrp', 'Corr'), expected):
                    self.assertEqual(w.counter_values[name].text(), value)
            finally:
                w.close()
                w.deleteLater()

    def test_zini_rows_pending_on_win_and_loss(self):
        self.assertIn('Bounded best-so-far', ui.ZINI_NOTE)
        self.assertIn('not an exact minimum', ui.ZINI_NOTE)
        self.assertEqual(self.window.zini_status.text(), 'ZiNi: calculating...')
        for game in (10, 20):
            self.window.select_pair(game, 'stage3')
            for name in ('ZiNi', 'ZNE', 'ZNT'):
                self.assertEqual(self.window.counter_values[name].text(), '-')
                self.assertEqual(self.window.counter_values[name].toolTip(), ui.ZINI_NOTE)

    def complete_zini(self, clicks=5):
        self.window._zini_job.finish(clicks)
        self.window._poll_zini()

    def test_zini_starts_once_and_same_board_solver_switch_reuses_pending_job(self):
        w, job = self.window, self.window._zini_job
        self.assertEqual(len(job.starts), 1)
        self.assertIs(job.starts[0][0], w.reconstruction.board_snapshot)
        closes = job.closes
        w.solver_selector.setCurrentIndex(1)
        self.assertEqual(len(job.starts), 1)
        self.assertEqual(job.closes, closes)
        self.assertTrue(w._zini_timer.isActive())

    def test_zini_board_switch_cancels_pending_and_completed_cache_is_reused(self):
        w, job = self.window, self.window._zini_job
        token = job.token
        w.select_pair(20, 'stage2')
        self.assertEqual(job.cancelled, [token])
        self.assertEqual(len(job.starts), 2)
        self.complete_zini(7)
        key = (20, w.reconstruction.timeline.record.board_fingerprint)
        self.assertEqual(w._zini_cache, {key: 7})
        w.select_pair(10, 'stage2')  # the cancelled, unfinished board recomputes
        self.assertEqual(len(job.starts), 3)
        w.select_pair(20, 'stage3')
        self.assertEqual(len(job.starts), 3)
        self.assertEqual(w.counter_values['ZiNi'].text(), '7')
        self.assertFalse(w._zini_timer.isActive())
        self.assertIn('ready — bounded best-so-far', w.zini_status.text())

    def test_zini_completion_refreshes_current_frame_win_ratios_and_initial_masks(self):
        w = self.window
        w.select_frame(2)
        self.complete_zini(5)
        self.assertEqual(w.position.frame_index, 2)
        self.assertEqual(w.counter_values['ZiNi'].text(), '5')
        self.assertEqual(w.counter_values['ZNE'].text(), '2.5000')
        self.assertEqual(w.counter_values['ZNT'].text(), '2.5000')
        w.first_button.click()
        for name in ('ZNE', 'ZNT'):
            self.assertEqual(w.counter_values[name].text(), '-')
        self.assertEqual(w.counter_values['ZiNi'].text(), '5')
        w.select_pair(10, 'stage3')
        w.select_frame(1)
        self.assertEqual(w.counter_values['ZiNi'].text(), '5')
        self.assertEqual(w.counter_values['ZNE'].text(), '5.0000')
        self.assertEqual(w.counter_values['ZNT'].text(), '5.0000')
        self.assertEqual(len(w._zini_job.starts), 1)

    def test_zini_prefix_denominators_include_wasted_but_not_in_active(self):
        original = self.bundle.exemplars[0]
        current = replace(original.stage2.frame_counters[1], active_clicks=3, wasted_clicks=4)
        game = replace(original, stage2=replace(original.stage2, frame_counters=(
            original.stage2.frame_counters[0], current, *original.stage2.frame_counters[2:])))
        w = ui.ExemplarBoardViewerWindow(replace(self.bundle, exemplars=(game, *self.bundle.exemplars[1:])))
        try:
            w.select_frame(1)
            w._zini_job.finish(5)
            w._poll_zini()
            self.assertEqual(w.counter_values['ZNE'].text(), '0.7143')
            self.assertEqual(w.counter_values['ZNT'].text(), '1.6667')
        finally:
            w.close()
            w.deleteLater()

    def test_loss_zini_numeric_but_zne_znt_unavailable_at_every_frame(self):
        w = self.window
        w.select_pair(20, 'stage3')
        self.complete_zini(3)
        for k in range(w.action_count + 1):
            w.select_frame(k)
            self.assertEqual(w.counter_values['ZiNi'].text(), '3')
            for name in ('ZNE', 'ZNT'):
                self.assertEqual(w.counter_values[name].text(), '-')

    def test_zini_failure_or_stale_result_is_unavailable_not_cached(self):
        w = self.window
        cases = ({'token': -1, 'clicks': 999, 'error': None},
                 {'token': w._zini_token, 'clicks': 5},
                 {'token': w._zini_token, 'clicks': None, 'error': 'private traceback'},
                 {'token': w._zini_token, 'clicks': True, 'error': None})
        for result in cases:
            w._zini_job.result = result
            w._poll_zini()
            self.assertEqual(w._zini_cache, {})
            self.assertEqual(w.zini_status.text(), 'ZiNi: unavailable — calculation failed')
            for name in ('ZiNi', 'ZNE', 'ZNT'):
                self.assertEqual(w.counter_values[name].text(), '-')
            self.assertNotIn('private traceback', w.zini_status.text())

    def test_navigation_overlay_and_playback_never_manage_zini_job(self):
        w, job = self.window, self.window._zini_job
        with patch.object(job, 'start', side_effect=AssertionError('start')), \
             patch.object(job, 'close', side_effect=AssertionError('close')):
            w.select_action(3)
            w.set_before(True)
            w.set_before(False)
            w.frame_slider.setValue(1)
            w.first_button.click()
            w.next_button.click()
            w.previous_button.click()
            w.last_button.click()
            w.first_button.click()
            w.action_entry.setValue(2)
            w.action_go.click()
            w.answer_checkbox.setChecked(True)
            w.answer_checkbox.setChecked(False)
            w.play_button.click()
            for _ in range(w.action_count):
                self.index_tick(w)
            clock = self.time_mode()
            w.select_time(200123)
            w.play_button.click()
            clock.ns = 10000000
            w._advance_playback()
            w.playback_speed.setValue(2)
            w.answer_checkbox.setChecked(True)
            w.index_interval.setValue(20)  # Inactive-mode configuration must not change time tick.
            self.assertEqual(w.play_timer.interval(), 16)
            w.playback_mode.setCurrentText('Index')
            self.index_tick(w)
            w.playback_mode.setCurrentText('Model C Time')
            w.frame_slider.setValue(300123)
            w.solver_selector.setCurrentIndex(1)
        self.assertEqual(len(job.starts), 1)

    def test_close_stops_zini_timer_and_cancels_job(self):
        w, job = self.window, self.window._zini_job
        self.assertTrue(w._zini_timer.isActive())
        token = job.token
        w.close()
        self.assertFalse(w._zini_timer.isActive())
        self.assertFalse(job.active)
        self.assertEqual(job.cancelled, [token])

    def test_modeled_counter_summary_exact_prefix_before_after_and_playback(self):
        w = self.window
        w.select_action(3)
        for before, expected in ((True, ('0.271', '2.167', '3.6915', '7.3829')),
                                 (False, ('0.397', '1.588', '5.0390', '7.5586'))):
            w.set_before(before)
            for name, value in zip(('Time (Model C)', 'Est Time (Model C)',
                                    '3BV/s (Model C)', 'CPS (Model C)'), expected):
                self.assertEqual(w.counter_values[name].text(), value)
        w.select_frame(0)
        w.play_button.click()
        self.index_tick(w)
        self.assertEqual(w.counter_values['Time (Model C)'].text(), '0.126')
        self.assertEqual(w.counter_values['Est Time (Model C)'].text(), '1.008')
        self.assertEqual(w.counter_values['3BV/s (Model C)'].text(), '7.9362')
        self.assertEqual(w.counter_values['CPS (Model C)'].text(), '7.9362')

    def test_win_and_loss_counter_model_time_authority(self):
        w = self.window
        w.last_button.click()
        self.assertEqual(w.counter_values['Time (Model C)'].text(), '1.306')
        self.assertEqual(w.counter_values['Est Time (Model C)'].text(), '1.306')
        self.assertEqual(w.counter_values['3BV/s (Model C)'].text(), '6.1260')
        self.assertEqual(w.counter_values['CPS (Model C)'].text(), '6.8917')
        w.select_pair(20, 'stage2')
        w.last_button.click()
        self.assertEqual(w.counter_values['Time (Model C)'].text(), '0.756')
        self.assertEqual(w.counter_values['Est Time (Model C)'].text(), '3.026')
        self.assertIn('through termination, not time-to-win', w.counter_values['Time (Model C)'].toolTip())
        self.assertEqual(w.counter_values['Est Time (Model C)'].toolTip(), ui.ESTIMATE_NOTE)

    def test_model_costs_follow_displayed_frame_and_selected_action_separately(self):
        w = self.window
        timeline = w.reconstruction.timeline
        self.assertEqual(w.model_values['Selected Action Model C Cost'].text(), 'unavailable')
        self.assertEqual(w.model_values['Cumulative Model C Time'].text(), '0 us (0.000000 s)')
        w.select_action(3)
        w.set_before(True)
        self.assertEqual(w.model_values['Selected Action Model C Cost'].text(), f'{timeline.actions[2].modeled_action_us} us')
        self.assertEqual(w.model_values['Cumulative Model C Time'].text(), '270896 us (0.270896 s)')
        w.set_before(False)
        self.assertEqual(w.model_values['Cumulative Model C Time'].text(), '396901 us (0.396901 s)')
        w.select_action(1)
        w.set_before(True)
        self.assertEqual(w.model_values['Cumulative Model C Time'].text(), '0 us (0.000000 s)')

    def test_model_tab_exact_rows_and_initial_current_unavailability(self):
        w = self.window
        self.assertEqual(tuple(w.model_values), (
            'Selected Action Model C Cost', 'Cumulative Model C Time',
            'Current Modeled Est Time', 'Current Modeled 3BV/s', 'Current Modeled CPS',
            'Final Model C Time', 'Final Modeled 3BV/s', 'Final Modeled CPS', 'Initial Model C cursor'))
        for name in ('Current Modeled Est Time', 'Current Modeled 3BV/s', 'Current Modeled CPS'):
            self.assertEqual(w.model_values[name].text(), '-')
        self.assertEqual(w.counter_values['Time (Model C)'].text(), '0.000')
        for name in ('Est Time (Model C)', '3BV/s (Model C)', 'CPS (Model C)'):
            self.assertEqual(w.counter_values[name].text(), '-')

    def test_model_seconds_formatting_is_exact_even_beyond_float_precision(self):
        for us, expected in (
            (0, '0 us (0.000000 s)'),
            (1, '1 us (0.000001 s)'),
            (1_000_000, '1000000 us (1.000000 s)'),
            (30_355_982, '30355982 us (30.355982 s)'),
            (9_007_199_254_740_993, '9007199254740993 us (9007199254.740993 s)'),
        ):
            with self.subTest(us=us):
                self.assertEqual(ui._modeled_time(us), expected)

    def test_current_modeled_metrics_before_after_use_prefix_not_selected_or_final(self):
        w = self.window
        w.select_action(3)
        final = {name: w.model_values[name].text() for name in
                 ('Final Model C Time', 'Final Modeled 3BV/s', 'Final Modeled CPS')}
        for before, expected in (
            (True, ('2.167168 s', '3.6915', '7.3829')),
            (False, ('1.587604 s', '5.0390', '7.5586')),
        ):
            w.set_before(before)
            for name, value in zip(('Current Modeled Est Time', 'Current Modeled 3BV/s',
                                    'Current Modeled CPS'), expected):
                self.assertEqual(w.model_values[name].text(), value)
            for name, value in final.items():
                self.assertEqual(w.model_values[name].text(), value)
            self.assertEqual(w.counter_values['3BV/s (Model C)'].text(), expected[1])
            self.assertEqual(w.counter_values['CPS (Model C)'].text(), expected[2])

    def test_current_zero_completed_3bv_with_positive_cost_keeps_cps_defined(self):
        game = self.bundle.exemplars[0]
        counters = list(game.stage2.frame_counters)
        counters[1] = replace(counters[1], completed_3bv=0)
        game = replace(game, stage2=replace(game.stage2, frame_counters=tuple(counters)))
        w = ui.ExemplarBoardViewerWindow(replace(self.bundle, exemplars=(game, *self.bundle.exemplars[1:])))
        try:
            w.select_frame(1)
            self.assertEqual(w.model_values['Current Modeled 3BV/s'].text(), '0.0000')
            self.assertEqual(w.model_values['Current Modeled CPS'].text(), '7.9362')
            self.assertEqual(w.model_values['Current Modeled Est Time'].text(), '-')
            self.assertEqual(w.counter_values['Est Time (Model C)'].text(), '-')
            self.assertEqual(w.counter_values['3BV/s (Model C)'].text(), '0.0000')
            self.assertEqual(w.counter_values['CPS (Model C)'].text(), '7.9362')
        finally:
            w.close()
            w.deleteLater()

    def test_win_final_current_metrics_reconcile_with_complete_run_values(self):
        w = self.window
        w.last_button.click()
        self.assertEqual(w.reconstruction.frame_counters[-1].completed_3bv,
                         w.reconstruction.board_reference.total_3bv)
        self.assertEqual(w.model_values['Cumulative Model C Time'].text(), '1305919 us (1.305919 s)')
        self.assertEqual(w.model_values['Final Model C Time'].text(), '1305919 us (1.305919 s)')
        self.assertEqual(w.model_values['Current Modeled Est Time'].text(), '1.305919 s')
        self.assertEqual(w.model_values['Current Modeled 3BV/s'].text(), '6.1260')
        self.assertEqual(w.model_values['Current Modeled CPS'].text(), '6.8917')
        self.assertEqual(w.model_values['Final Modeled 3BV/s'].text(), '8000000/1305919 = 6.1260 (presentation)')
        self.assertEqual(w.model_values['Final Modeled CPS'].text(), '9000000/1305919 = 6.8917 (presentation)')
        self.assertIn('final rates describe this completed run', w.cost_note.text())

    def test_loss_current_estimate_is_extrapolation_not_observed_finish_or_time_to_win(self):
        w = self.window
        w.select_pair(20, 'stage2')
        w.last_button.click()
        self.assertEqual(w.model_values['Current Modeled Est Time'].text(), '3.025604 s')
        self.assertEqual(w.model_values['Final Model C Time'].text(), '756401 us (0.756401 s)')
        note = w.model_values['Current Modeled Est Time'].toolTip()
        self.assertIn('extrapolates total 3BV', note)
        self.assertIn('displayed prefix', note)
        self.assertIn('not observed gameplay time or a predicted solver finish', note)
        self.assertIn('not time-to-win, including on LOSS', note)
        self.assertIn('through termination — not time-to-win', w.cost_note.text())

    def test_model_final_rates_use_completed_3bv_and_actions_over_model_seconds(self):
        w = self.window
        for game in (10, 20):
            w.select_pair(game, 'stage3')
            cost = w.reconstruction.timeline.total_modeled_us
            b = w.reconstruction.final_counters.completed_3bv
            self.assertEqual(w.model_values['Final Model C Time'].text(),
                             f'{cost} us ({Decimal(cost).scaleb(-6):.6f} s)')
            self.assertEqual(w.model_values['Final Modeled 3BV/s'].text(), f'{b * 1000000}/{cost} = {b * 1000000/cost:.4f} (presentation)')
            self.assertIn(f'{w.action_count * 1000000}/{cost}', w.model_values['Final Modeled CPS'].text())
            rates = tuple(w.model_values[name].text() for name in ('Final Modeled 3BV/s', 'Final Modeled CPS'))
            w.last_button.click()
            self.assertEqual(tuple(w.model_values[name].text() for name in ('Final Modeled 3BV/s', 'Final Modeled CPS')), rates)
            if game == 20:
                self.assertIn('through termination — not time-to-win', w.cost_note.text())

    def test_exact_fraction_none_zero_and_candidate_scope(self):
        w = self.window
        w.select_action(3)
        self.assertEqual(w.action_values['Target mine probability'].text(), f'{RISK.numerator}/{RISK.denominator}')
        self.assertEqual(w.action_values['Minimum available mine probability'].text(), '1/3')
        self.assertEqual(w.action_values['Decision compute (ns)'].text(), '0')
        self.assertEqual(w.action_values['Candidate count'].text(), '4')
        w.select_pair(10, 'stage3')
        w.select_action(4)
        self.assertEqual(w.action_values['Candidate count'].text(), 'unavailable')
        w.select_action(1)
        self.assertEqual(w.action_values['Decision compute (ns)'].text(), 'unavailable')
        self.assertEqual(w.action_values['Inference category'].text(), 'unavailable')
        self.assertIn('exact-minimum-risk', ui.CANDIDATE_NOTE)
        self.assertIn('analysis + planning', ui.COMPUTE_NOTE)

    def test_initial_context_has_no_fabricated_event_facts(self):
        w = self.window
        for name in ('Selected ordinal','Action type','Current target','Previous recorded target',
                     'dx','dy','d²','Selected Model C action us','Inference category','Target mine probability',
                     'Candidate count','Decision compute (ns)','Recorded safe reveal delta',
                     'Reconstructed new-safe count','Explicit flag delta'):
            self.assertEqual(w.action_values[name].text(), 'unavailable')
        self.assertEqual(w.action_values['Displayed frame'].text(), '0')
        self.assertEqual(w.action_values['Cumulative Model C us'].text(), '0')
        self.assertIsNone(w.board.targets.current_target)

    def test_board_mouse_input_does_not_play_or_navigate(self):
        position = self.window.position
        for button in (Qt.LeftButton, Qt.RightButton, Qt.MiddleButton):
            QTest.mouseClick(self.window.board.cells[0, 0], button)
        self.assertEqual(self.window.position, position)
        self.assert_frame()

    def test_five_areas_and_scroll_containers_remain_available_on_small_window(self):
        from PyQt5.QtWidgets import QGroupBox
        titles = [group.title() for group in self.window.findChildren(QGroupBox)]
        self.assertCountEqual(titles, [
            'Board / Solver Reference', 'Classic Counters',
            'Model C', 'Action Context', 'Board Presentation — Public View',
        ])
        self.window.resize(800, 600)
        self.app.processEvents()
        self.assertIs(self.window.board_scroll.widget(), self.window.board)
        self.assertEqual([self.window.fact_tabs.tabText(i) for i in range(4)],
                         ['Reference', 'Counters', 'Model C', 'Action'])
        for scroll in self.window.fact_scrolls.values():
            self.assertTrue(scroll.widgetResizable())
        self.assertEqual(self.window.board.width(), self.window.reconstruction.board_snapshot.width * 28)

    def test_desktop_initial_size_and_fact_tabs_avoid_stacked_scroll(self):
        screen = MagicMock()
        screen.availableGeometry.return_value = QRect(0, 0, 1920, 1040)
        with patch.object(ui.ExemplarBoardViewerWindow, 'screen', return_value=screen):
            w = ui.ExemplarBoardViewerWindow(self.bundle)
        try:
            # Geometry-only fixture for the Expert board's exact pixel extent.
            w.board.setFixedSize(30 * ui.CELL_SIZE, 16 * ui.CELL_SIZE)
            w.show()
            self.app.processEvents()
            self.assertLessEqual(w.frameGeometry().width(), 1920)
            self.assertLessEqual(w.frameGeometry().height(), 1040)
            self.assertGreaterEqual(w.board_scroll.viewport().width(), 30 * ui.CELL_SIZE)
            self.assertGreaterEqual(w.board_scroll.viewport().height(), 16 * ui.CELL_SIZE)
            self.assertEqual(w.content_scroll.verticalScrollBar().maximum(), 0)
            self.assertEqual(w.content_scroll.horizontalScrollBar().maximum(), 0)
            for index, (title, scroll) in enumerate(w.fact_scrolls.items()):
                w.fact_tabs.setCurrentIndex(index)
                self.app.processEvents()
                self.assertEqual(scroll.verticalScrollBar().maximum(), 0, title)
                self.assertEqual(scroll.horizontalScrollBar().maximum(), 0, title)
            for values, title in ((w.reference_values, 'Reference'), (w.counter_values, 'Counters'),
                                  (w.model_values, 'Model C'), (w.action_values, 'Action')):
                self.assertTrue(all(w.fact_scrolls[title].widget().isAncestorOf(label)
                                    for label in values.values()))
        finally:
            w.close()
            w.deleteLater()

    def test_small_available_screen_caps_initial_window_with_scroll_fallback(self):
        for width, height in ((800, 600), (640, 480)):
            with self.subTest(screen=(width, height)):
                screen = MagicMock()
                screen.availableGeometry.return_value = QRect(0, 0, width, height)
                with patch.object(ui.ExemplarBoardViewerWindow, 'screen', return_value=screen):
                    w = ui.ExemplarBoardViewerWindow(self.bundle)
                try:
                    w.show()
                    w.fact_tabs.setCurrentIndex(3)
                    self.app.processEvents()
                    self.assertLessEqual(w.frameGeometry().width(), width)
                    self.assertLessEqual(w.frameGeometry().height(), height)
                    self.assertGreater(w.fact_scrolls['Action'].verticalScrollBar().maximum(), 0)
                    for widget in (w.first_button, w.play_button, w.action_go,
                                   w.playback_mode, w.index_interval, w.playback_speed,
                                   w.route_checkbox, w.answer_checkbox):
                        # Scroll to the actual control, not a spinbox's internal
                        # line-edit focus-proxy rectangle used by ensureWidgetVisible.
                        center = widget.mapTo(w.content_scroll.widget(), widget.rect().center())
                        w.content_scroll.ensureVisible(center.x(), center.y())
                        viewport = w.content_scroll.viewport()
                        self.assertTrue(viewport.rect().contains(widget.mapTo(viewport, widget.rect().center())),
                                        widget.accessibleName() or type(widget).__name__)
                finally:
                    w.close()
                    w.deleteLater()

    def test_authority_labels_preserve_exact_semantic_boundaries(self):
        texts = [label.text() for label in self.window.findChildren(QLabel)]
        self.assertIn('Reconstructed Counters — displayed frame; current Engine semantics', texts)
        self.assertIn('Time rows use Model C, not historical elapsed time.', texts)
        self.assertIn('Active/wasted is mechanical, not a strategy grade.', texts)
        self.assertIn('3BV / Ops / isolated number count = answer-derived board references, '
                      'not solver-visible evidence.', texts)
        self.assertEqual(self.window.answer_checkbox.text(), 'Show hidden answers — reference overlay')
        self.assertEqual(ui.TRANSITION_NOTE, 'Action-target transition — not recorded cursor trajectory')
        self.assertTrue(any(ui.TRANSITION_NOTE in text for text in texts))
        model_note = (
            'Both timelines are post-hoc Model C evaluations of persisted actions. '
            'Stage 2 did not natively declare Model C; Stage 3 declared it during collection, '
            'but these events retain no native per-action cost/cursor fields. '
            'This is modeled physical execution time, not Replay elapsed, CPU decision '
            'time or recorded cursor trajectory.'
        )
        self.assertEqual(ui.MODEL_NOTE, model_note)
        self.assertNotIn(model_note, texts)
        self.assertIn(model_note, [label.toolTip() for label in self.window.findChildren(QLabel)])
        self.assertIn('Model C = modeled physical execution cost; not Replay time or recorded cursor motion.', texts)
        self.assertEqual(self.window.action_values['Candidate count'].toolTip(), ui.CANDIDATE_NOTE)
        self.assertEqual(self.window.action_values['Decision compute (ns)'].toolTip(), ui.COMPUTE_NOTE)
        self.assertNotIn(ui.CANDIDATE_NOTE, texts)
        self.assertNotIn(ui.COMPUTE_NOTE, texts)

    def test_construction_navigation_and_toggles_do_no_domain_work(self):
        with ExitStack() as guards:
            for owner, name in ((evidence_module,'load_accepted_exemplar_evidence'),
                                (evidence_module.boards,'generate_board'),
                                (telemetry_repository,'connect_database_readonly'),
                                (telemetry_repository,'connect_database'),
                                (MinesweeperEngine,'__init__'), (MinesweeperEngine,'step'),
                                (MinesweeperEngine,'reset_with_mines'),
                                (reconstruction_module,'reconstruct_board'),
                                (timeline_analytics,'project_timeline'),
                                (modeled,'authenticate_model_c')):
                guards.enter_context(patch.object(owner, name, side_effect=AssertionError(name)))
            window = ui.ExemplarBoardViewerWindow(self.bundle)
            try:
                for pair in window._positions:
                    window.select_pair(*pair)
                    window.route_checkbox.setChecked(True)
                    window.select_frame(window.action_count)
                    window.set_before(True)
                    window.answer_checkbox.setChecked(True)
                    window.answer_checkbox.setChecked(False)
                    window.select_frame(0)
                    window.play_button.click()
                    for _ in range(window.action_count):
                        self.index_tick(window)
                    self.assertFalse(window.play_timer.isActive())
                    clock = FakeWallClock()
                    window._wall_clock = clock
                    window.playback_mode.setCurrentText('Model C Time')
                    window.select_time(1)
                    window.play_button.click()
                    clock.ns = 100000000
                    window._advance_playback()
                    window.playback_speed.setValue(2)
                    window.index_interval.setValue(20)
                    window.frame_slider.setValue(200123)
                    window.route_checkbox.setChecked(False)
                    window.route_checkbox.setChecked(True)
                    window.playback_mode.setCurrentText('Index')
                self.assertCountEqual(window.findChildren(QTimer), [window.play_timer, window._zini_timer])
            finally:
                window.close()
                window.deleteLater()

    def test_no_forbidden_ui_imports_or_domain_execution_paths(self):
        tree = ast.parse(inspect.getsource(ui))
        forbidden = {'sqlite3','telemetry_repository','benchmark_board','benchmark_modeled_time',
                     'timeline_analytics','simple_runner','simple_decision','stage3_runner','stage3_planner',
                     'representative_boards','ui_manager','zini_explorer','zini_calculator','zini_advanced','zini_metric_worker',
                     'stage3_visualizer_ui','same_board_comparison_ui','subprocess','time'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertTrue(all(a.name.split('.')[0] not in forbidden for a in node.names))
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn(node.module.split('.')[0], forbidden)
                self.assertTrue(all(a.name not in ('MinesweeperEngine','load_accepted_exemplar_evidence') for a in node.names))


class LauncherTests(unittest.TestCase):
    def test_both_paths_required_and_arbitrary_options_rejected(self):
        for args in ([], ['--stage2-db','s2'], ['--stage3-db','s3'],
                     ['--stage2-db','s2','--stage3-db','s3','--game-index','10']):
            with self.subTest(args=args), redirect_stderr(io.StringIO()), \
                    patch.object(launcher,'load_accepted_exemplar_evidence') as load, \
                    self.assertRaises(SystemExit) as raised:
                launcher.main(args)
            self.assertEqual(raised.exception.code, 2)
            load.assert_not_called()

    def test_one_loader_call_correct_roles_exact_bundle_then_show_and_event_loop(self):
        bundle, calls = object(), []
        app, window = MagicMock(), MagicMock()
        app.exec_.return_value = 7
        with patch.object(launcher,'load_accepted_exemplar_evidence', side_effect=lambda *args: calls.append('load') or bundle) as load, \
                patch.object(launcher,'QApplication') as app_type, \
                patch.object(launcher,'ExemplarBoardViewerWindow', side_effect=lambda data: calls.append('window') or window) as viewer:
            app_type.instance.return_value = None
            app_type.return_value = app
            self.assertEqual(launcher.main(['--stage2-db','s2 #%.sqlite3','--stage3-db','s3.sqlite3']), 7)
        load.assert_called_once_with(Path('s2 #%.sqlite3'), Path('s3.sqlite3'))
        viewer.assert_called_once_with(bundle)
        window.show.assert_called_once()
        app.exec_.assert_called_once()
        app_type.assert_called_once()
        self.assertEqual(calls, ['load','window'])

    def test_existing_application_is_reused(self):
        app = MagicMock()
        app.exec_.return_value = 0
        with patch.object(launcher,'load_accepted_exemplar_evidence'), \
                patch.object(launcher,'ExemplarBoardViewerWindow'), patch.object(launcher,'QApplication') as app_type:
            app_type.instance.return_value = app
            self.assertEqual(launcher.main(['--stage2-db','s2','--stage3-db','s3']), 0)
            app_type.assert_not_called()

    def test_load_failure_reports_and_creates_no_qapplication_or_viewer(self):
        output = io.StringIO()
        with patch.object(launcher,'load_accepted_exemplar_evidence', side_effect=launcher.ExemplarEvidenceError('hash mismatch')), \
                patch.object(launcher,'QApplication') as app, patch.object(launcher,'ExemplarBoardViewerWindow') as viewer, \
                redirect_stderr(output):
            self.assertEqual(launcher.main(['--stage2-db','s2','--stage3-db','s3']), 1)
        self.assertIn('Cannot load accepted exemplar evidence: hash mismatch', output.getvalue())
        app.assert_not_called()
        app.instance.assert_not_called()
        viewer.assert_not_called()


if __name__ == '__main__':
    unittest.main()
