"""Observable cursor/probability UI contracts, fake owner and deterministic clock."""

import os
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt5.QtCore import QCoreApplication, QEvent, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QWidget

from core_engine import Action
from live_auto_cursor import LiveAutoCursorOverlay
from live_policy import POLICY_K, POLICY_SIMPLE, POLICY_V1
from replay_model import ReplayBoard, ReplayData, ReplayEvent
from replay_player import ReplayPlayer
from ui_manager import ChordMode
import tests.test_live_auto as v1_ui
import tests.test_live_k_ui as k_ui


class CursorOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.parent = QWidget()
        self.now = [0.0]
        self.overlay = LiveAutoCursorOverlay(self.parent, clock=lambda: self.now[0])
        self.addCleanup(self.close_parent)

    def close_parent(self):
        self.overlay.clear()
        self.parent.close()
        self.parent.deleteLater()
        # This standalone fixture has no Main.closeEvent. Reap its QObject
        # tree before a later test enters Qt's event loop.
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def test_linear_motion_has_existing_duration_and_holds_at_target(self):
        o = self.overlay
        o.set_available(True)
        o.reserve('reservation', (1, 2), (5, 6), 200)
        self.assertEqual(o.position, (1, 2))
        self.now[0] = .05
        self.assertEqual(o.position, (2, 3))
        self.now[0] = .2
        o._timeout_slot()
        self.assertEqual(o.position, (5, 6))
        self.assertFalse(o._timer.isActive())
        self.now[0] = 100.0
        self.assertEqual(o.position, (5, 6))
        self.assertEqual(o._actual, (1, 2))
        o.cancel()
        self.assertEqual(o.position, (1, 2))

    def test_zero_interval_jumps_without_timer_or_extra_delay(self):
        o = self.overlay
        o.reserve('zero', (0, 0), (4, 2), 0)
        self.assertEqual(o.position, (4, 2))
        self.assertFalse(o._timer.isActive())
        self.assertIsNone(o._motion)
        self.assertEqual(o._actual, (0, 0))

    def test_stale_visual_callback_cannot_change_new_reservation_or_actual(self):
        o = self.overlay
        o.reserve('old', (0, 0), (8, 8), 200)
        old = o._timeout_slot
        o.set_actual((1, 1))
        o.reserve('new', (1, 1), (3, 1), 1000)
        self.now[0] = .25
        before = (o.position, o._reservation, o._generation)
        old()
        self.assertEqual((o.position, o._reservation, o._generation), before)
        o.clear()
        old()
        self.assertEqual(o.position, (1, 1))
        self.assertTrue(o.isHidden())
        self.assertFalse(o._timer.isActive())

    def test_display_toggle_keeps_motion_clock_generation_and_position(self):
        o = self.overlay
        o.set_available(True)
        o.reserve('visible', (0, 0), (4, 0), 1000)
        generation, motion, timer_id = o._generation, o._motion, o._timer.timerId()
        o.set_display_enabled(False)
        self.now[0] = .5
        self.assertEqual(o.position, (2, 0))
        o.set_display_enabled(True)
        self.assertEqual((o._generation, o._motion, o._timer.timerId()), (generation, motion, timer_id))
        self.assertEqual(o.position, (2, 0))

    def test_cell_centers_resize_and_mouse_transparency(self):
        o = self.overlay
        o.set_actual((2, 3))
        o.set_cell_size(24)
        self.assertEqual((o.pixel_position.x(), o.pixel_position.y()), (60, 84))
        o.set_cell_size(40)
        self.assertEqual((o.pixel_position.x(), o.pixel_position.y()), (100, 140))
        self.assertTrue(o.testAttribute(Qt.WA_TransparentForMouseEvents))
        self.assertEqual(o.focusPolicy(), Qt.NoFocus)
        self.assertEqual(o._actual, (2, 3))


class KFeedbackUITests(unittest.TestCase):
    # Reuse only the existing fixture methods, not its test collection.
    close_ui = k_ui.LiveKUITests.close_ui
    start = k_ui.LiveKUITests.start
    tick = k_ui.LiveKUITests.tick
    apply_initial = k_ui.LiveKUITests.apply_initial

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        k_ui.LiveKUITests.setUp(self)
        self.now = [0.0]
        self.overlay = self.ui.auto_cursor_overlay
        self.overlay._clock = lambda: self.now[0]
        self.ui._pacing_clock_ns = lambda: 0  # Explicit deterministic input clock; tick advances it.
        self.ui.simple_auto_interval_spin.setValue(2000)

    def guess_pending(self):
        self.apply_initial()
        self.job.deliver_ack()
        self.job.compute()
        p = self.job.pending
        self.assertTrue(p.is_guess)
        return p

    def test_default_on_without_owner_hidden_and_analysis_only_anchor(self):
        self.assertTrue(self.ui.auto_cursor_checkbox.isChecked())
        self.assertTrue(self.overlay.isHidden())
        for enabled in (False, True, False, True):
            self.ui.auto_cursor_checkbox.setChecked(enabled)
        self.assertEqual(self.job.requests, [])
        self.ui.on_analyze_current()
        self.job.compute()
        self.assertFalse(self.overlay.isHidden())
        self.assertEqual(self.overlay.position, (0, 0))
        self.assertIsNone(self.overlay._reservation)
        self.assertFalse(self.overlay._timer.isActive())
        self.assertEqual(self.ui._live_action_count, 0)

    def test_guess_wait_shows_exact_risk_and_reuses_pending_through_display_toggles(self):
        p = self.guess_pending()
        result = self.ui._analysis_result
        self.assertIn('지뢰 확률', self.ui.analysis_status_label.text())
        self.assertIn('추측 대기', self.ui.analysis_status_label.text())
        self.assertTrue(self.ui._buttons[(p.x, p.y)].probability_text)
        self.assertEqual(self.overlay.position, self.ui._v1_cursor)
        before = (self.ui._v1_timer_nonce, len(self.job.requests), len(self.job.validations),
                  self.ui._live_action_count, dict(self.ui.live_auto_totals))
        with patch.object(type(self.job.owner.session), 'analyze_decision', side_effect=AssertionError('display analyze')), \
                patch.object(self.job.owner, '_select', side_effect=AssertionError('display select')):
            for enabled in (False, True, False, True):
                self.ui.probability_checkbox.setChecked(enabled)
                self.ui.auto_cursor_checkbox.setChecked(enabled)
                self.assertEqual(bool(self.ui._buttons[(p.x, p.y)].probability_text), enabled)
        self.assertIs(self.ui._v1_pending, p)
        self.assertIs(self.ui._analysis_result, result)
        self.assertEqual(before, (self.ui._v1_timer_nonce, len(self.job.requests), len(self.job.validations),
                                  self.ui._live_action_count, dict(self.ui.live_auto_totals)))

    def test_positive_interval_moves_only_visual_cursor_then_waits_for_k_admission(self):
        p = self.guess_pending()
        actual = self.ui._v1_cursor
        self.ui.allow_guess_checkbox.setChecked(True)
        self.now[0] = 1.0
        expected = tuple((a + b) / 2 for a, b in zip(actual, (p.x, p.y)))
        self.assertEqual(self.overlay.position, expected)
        self.assertEqual(self.ui._v1_cursor, actual)
        self.assertEqual(self.ui._live_action_count, 1)
        self.now[0] = 2.0
        self.tick()
        self.assertEqual(self.overlay.position, (p.x, p.y))
        self.assertEqual(self.job.state, 'validating')
        self.now[0] = 20.0
        self.assertEqual(self.overlay.position, (p.x, p.y))
        self.assertEqual(self.ui._v1_cursor, actual)
        self.assertEqual(self.ui._live_action_count, 1)

    def test_hidden_cursor_and_probability_toggles_do_not_revoke_admission_or_change_cost(self):
        p = self.guess_pending()
        self.ui.allow_guess_checkbox.setChecked(True)
        self.tick()
        nonce, validations = self.ui._k_validation_nonce, len(self.job.validations)
        self.ui.auto_cursor_checkbox.setChecked(False)
        self.ui.probability_checkbox.setChecked(False)
        self.assertEqual(self.ui._k_validation_nonce, nonce)
        self.assertEqual(len(self.job.validations), validations)
        before_cost = self.ui.live_auto_totals['k_modeled_us']
        admitted = self.job.deliver_admission()
        self.assertEqual(self.ui._live_action_count, 2)
        self.assertEqual(self.ui._v1_cursor, (p.x, p.y))
        self.assertEqual(self.overlay.position, (p.x, p.y))
        self.assertEqual(self.ui.live_auto_totals['k_modeled_us'], before_cost + p.modeled_action_us)
        self.assertEqual(len(self.ui._replay_recorder.events), 2)
        self.assertEqual(self.ui._replay_recorder.source_type, 'algorithm')
        self.assertIsNone(self.ui._mouse_trace_recorder.snapshot())
        self.assertTrue(all(b.probability_text == '' for b in self.ui._buttons.values()))
        self.ui.auto_cursor_checkbox.setChecked(True)
        self.assertFalse(self.overlay.isHidden())
        self.assertEqual(self.overlay.position, self.ui._v1_cursor)
        self.ui._on_k_admitted(admitted)
        self.assertEqual(self.ui._live_action_count, 2)

    def test_pause_validation_and_resume_keeps_exact_pending_and_discards_old_callbacks(self):
        p = self.guess_pending()
        self.ui.allow_guess_checkbox.setChecked(True)
        old_draw = self.overlay._timeout_slot
        old_input = self.ui._simple_auto_timeout_slot
        self.tick()
        self.ui.simple_auto_checkbox.setChecked(False)
        self.assertEqual(self.overlay.position, self.ui._v1_cursor)
        old_draw()
        old_input()
        self.job.deliver_admission()
        self.assertEqual(self.ui._live_action_count, 1)
        self.assertIs(self.ui._v1_pending, p)
        self.assertEqual(self.overlay.position, self.ui._v1_cursor)
        self.ui.simple_auto_checkbox.setChecked(True)
        reservation = self.ui._v1_timer_reservation
        old_draw()
        old_input()
        self.assertEqual(self.ui._v1_timer_reservation, reservation)
        self.tick()
        self.job.deliver_admission()
        self.assertEqual(self.ui._live_action_count, 2)
        self.assertEqual(len(self.job.requests), 2)

    def test_guess_off_and_interval_change_discard_old_motion_without_new_analysis(self):
        p = self.guess_pending()
        self.ui.allow_guess_checkbox.setChecked(True)
        old_draw, old_input = self.overlay._timeout_slot, self.ui._simple_auto_timeout_slot
        self.now[0] = 1
        self.ui.simple_auto_interval_spin.setValue(0)
        self.assertEqual(self.overlay.position, self.ui._v1_cursor)
        reservation = self.ui._v1_timer_reservation
        old_draw()
        old_input()
        self.assertEqual(self.ui._v1_timer_reservation, reservation)
        self.assertEqual(self.ui._live_action_count, 1)
        self.job.deliver_admission()  # Revoked early validation drains first.
        self.assertEqual(self.overlay.position, (p.x, p.y))
        self.tick()
        self.ui.allow_guess_checkbox.setChecked(False)
        self.job.deliver_admission()
        self.assertEqual(self.overlay.position, self.ui._v1_cursor)
        self.assertIsNone(self.overlay._reservation)
        self.assertEqual(self.ui._live_action_count, 1)
        self.assertIs(self.ui._v1_pending, p)
        self.assertEqual(len(self.job.requests), 2)

    def _manual_hit_test(self, buttons, mode, expected):
        self.ui.show()
        self.app.processEvents()
        self.ui.on_chord_mode_changed(mode)
        self.start()
        self.tick()
        cell = self.ui._buttons[(0, 0)]
        point = cell.mapToGlobal(cell.rect().center())
        self.assertIs(self.ui._cell_at_mouse_position(point), cell)
        self.assertIs(self.ui.board_container.childAt(self.ui.board_container.mapFromGlobal(point)), cell)
        position = self.ui.mapFromGlobal(point)
        native = self.ui.windowHandle()
        original_step = self.engine.step
        def step(*args, **kwargs):
            self.assertFalse(self.ui._v1_owned)
            self.assertTrue(self.overlay.isHidden())
            return original_step(*args, **kwargs)
        with patch.object(self.engine, 'step', side_effect=step) as called:
            for button in buttons:
                QTest.mousePress(native, button, pos=position)
            for button in reversed(buttons):
                QTest.mouseRelease(native, button, pos=position)
        self.assertEqual(called.call_count, 1)
        self.assertEqual(called.call_args.args, (0, 0, expected))
        self.assertEqual(self.ui._live_action_count, 1)
        self.assertFalse(self.ui._k_retired)
        self.job.deliver_admission()
        self.assertEqual(self.ui._live_action_count, 1)
        self.assertTrue(self.overlay.isHidden())

    def test_visible_overlay_passes_left_gesture_and_retires_before_step(self):
        self._manual_hit_test((Qt.LeftButton,), ChordMode.LEFT_CLICK, Action.OPEN)

    def test_visible_overlay_passes_right_gesture_and_retires_before_step(self):
        self._manual_hit_test((Qt.RightButton,), ChordMode.LEFT_CLICK, Action.FLAG)

    def test_visible_overlay_passes_both_gesture_and_retires_before_step(self):
        self._manual_hit_test((Qt.LeftButton, Qt.RightButton), ChordMode.BOTH_CLICK, Action.CHORD)

    def _expire(self, action):
        p = self.guess_pending()
        self.ui.allow_guess_checkbox.setChecked(True)
        draw, timeout = self.overlay._timeout_slot, self.ui._simple_auto_timeout_slot
        self.tick()
        before = self.ui._live_action_count
        action()
        after = self.ui._live_action_count
        draw()
        timeout()
        self.job.deliver_admission()
        self.assertEqual(self.ui._live_action_count, after)
        self.assertTrue(self.overlay.isHidden())
        self.assertFalse(self.overlay._timer.isActive())
        self.assertIsNone(self.ui._v1_pending)
        self.assertTrue(all(b.probability_text == '' for b in self.ui._buttons.values()))
        self.assertEqual(len(self.job.requests), 2)
        self.assertEqual(before, 1)

    def test_reset_expires_probability_and_cursor_late_callbacks(self):
        self._expire(self.ui.on_reset)
        self.assertEqual(self.overlay.position, (0, 0))

    def test_policy_change_expires_probability_and_cursor(self):
        self._expire(lambda: self.ui.live_policy_combo.setCurrentIndex(
            self.ui.live_policy_combo.findData(POLICY_SIMPLE)))

    def test_hard_retire_expires_probability_and_cursor(self):
        self._expire(lambda: self.ui._retire_v1_for_manual("manual handoff"))

    def test_error_expires_probability_and_cursor(self):
        self._expire(lambda: self.ui._fail_v1('synthetic validation error'))

    def test_replay_expires_probability_and_cursor(self):
        data = ReplayData(ReplayBoard(3, 3, 1, {(1, 1)}), (ReplayEvent(1, 0, 0, 'OPEN'),))
        self._expire(lambda: self.ui._enter_replay_mode(ReplayPlayer(data)))

    def test_close_discards_visual_callbacks_and_late_admission(self):
        self._expire(self.ui.close)

    def test_cell_resize_scroll_preserve_board_coordinates_and_reservation(self):
        self.ui.scroll_area.setFixedSize(120, 120)
        self.ui.show()
        self.app.processEvents()
        p = self.guess_pending()
        self.ui.allow_guess_checkbox.setChecked(True)
        self.now[0] = 1
        logical = self.overlay.position
        reservation = self.ui._v1_timer_reservation
        nonce = self.ui._v1_timer_nonce
        for size in (10, 24, 48):
            with self.subTest(size=size):
                self.ui.on_cell_size_changed(size)
                self.app.processEvents()
                self.assertEqual(self.overlay.position, logical)
                self.assertEqual(self.overlay.size(), self.ui.board_container.size())
                self.assertEqual(self.overlay.pixel_position.x(), (logical[0] + .5) * size)
                self.ui.scroll_area.horizontalScrollBar().setValue(20)
                self.ui.scroll_area.verticalScrollBar().setValue(20)
                if size >= 24:
                    self.assertEqual(self.ui.scroll_area.horizontalScrollBar().value(), 20)
                    self.assertEqual(self.ui.scroll_area.verticalScrollBar().value(), 20)
                    cell = self.ui._buttons[(2, 2)]
                    global_center = cell.mapToGlobal(cell.rect().center())
                    if self.ui.scroll_area.viewport().rect().contains(
                            self.ui.scroll_area.viewport().mapFromGlobal(global_center)):
                        self.assertIs(self.ui._cell_at_mouse_position(global_center), cell)
                self.assertEqual(self.overlay.position, logical)
                self.assertEqual(self.ui._v1_timer_reservation, reservation)
                self.assertEqual(self.ui._v1_timer_nonce, nonce)
                self.assertEqual(self.ui._live_action_count, 1)
        self.assertEqual(self.ui._v1_cursor, (0, 0))
        self.assertIs(self.ui._v1_pending, p)


class V1CursorUITests(unittest.TestCase):
    close_ui = v1_ui.LiveV1UITests.close_ui
    start = v1_ui.LiveV1UITests.start
    tick = v1_ui.LiveV1UITests.tick
    prepare_chord = v1_ui.LiveV1UITests.prepare_chord

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        v1_ui.LiveV1UITests.setUp(self)
        self.now = [0.0]
        self.overlay = self.ui.auto_cursor_overlay
        self.overlay._clock = lambda: self.now[0]
        self.ui._pacing_clock_ns = lambda: 0  # Preparation CPU time is not part of this interpolation fixture.
        self.ui.simple_auto_interval_spin.setValue(2000)

    def test_v1_motion_toggle_and_actual_chord_keep_cost_and_logical_cursor(self):
        job, p = self.prepare_chord()
        actual = self.ui._v1_cursor
        self.now[0] = 1
        self.assertEqual(self.overlay.position, tuple((a + b) / 2 for a, b in zip(actual, (p.x, p.y))))
        reservation, nonce = self.ui._v1_timer_reservation, self.ui._v1_timer_nonce
        for enabled in (False, True):
            self.ui.auto_cursor_checkbox.setChecked(enabled)
            self.ui.probability_checkbox.setChecked(enabled)
        self.assertEqual((self.ui._v1_timer_reservation, self.ui._v1_timer_nonce), (reservation, nonce))
        self.assertEqual(self.ui._v1_cursor, actual)
        self.tick()
        self.assertEqual(self.overlay.position, (p.x, p.y))
        self.assertEqual(self.ui._v1_cursor, (p.x, p.y))
        self.assertEqual(len(job.applied), 1)
        self.assertEqual(self.ui.live_auto_totals['v1_modeled_us'], p.modeled_action_us)
        self.assertEqual(len(self.ui._replay_recorder.events), 1)

    def test_v1_pause_resume_zero_interval_and_stale_callback(self):
        job, p = self.prepare_chord()
        draw, timeout = self.overlay._timeout_slot, self.ui._simple_auto_timeout_slot
        self.ui.simple_auto_checkbox.setChecked(False)
        draw()
        timeout()
        self.assertEqual(self.overlay.position, self.ui._v1_cursor)
        self.assertEqual(job.applied, [])
        self.ui.simple_auto_interval_spin.setValue(0)
        self.ui.simple_auto_checkbox.setChecked(True)
        self.assertEqual(self.overlay.position, (p.x, p.y))
        self.assertEqual(job.applied, [])
        timeout()
        self.assertEqual(job.applied, [])
        self.tick()
        self.assertEqual(len(job.applied), 1)
