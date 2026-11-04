"""Actual Qt controls/engine, fake owner delivery and a fake monotonic clock.

No child processes. Existing public fixtures retain their explicitly synthetic
board/preset seams. Real IPC timing is separately opt-in.
"""
from fractions import Fraction
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from PyQt5.QtCore import Qt
from PyQt5.QtTest import QSignalSpy, QTest
from PyQt5.QtWidgets import QApplication

from core_engine import Action
from live_pacing import FIXED, MODEL_C, PacingRate
from live_policy import POLICY_SIMPLE, POLICY_V1, POLICY_K, POLICY_K_LC0, POLICY_K_LC1
from replay_model import ReplayBoard, ReplayData, ReplayEvent
from replay_player import ReplayPlayer
from stage3_physical import action_cost, load_timing_table
from tests import test_live_auto as simple
from tests import test_display_stability as display
from tests.test_live_k_flag_adopt_ui import UI_MINES


def mode(ui, value=MODEL_C):
    ui.pacing_mode_combo.setCurrentIndex(ui.pacing_mode_combo.findData(value))
    if (value == MODEL_C and ui._v1_job.state == 'validating'
            and ui._k_validation_nonce is None):
        # Fixed mode now validates immediately. Drain its revoked response
        # before asserting the unchanged Model C wait-before-VALIDATE path.
        ui._v1_job.deliver_admission()


def edit(ui, value, cps=False):
    editor = ui.pacing_cps_edit if cps else ui.pacing_rate_edit
    editor.setText(str(value))
    editor.setModified(True)  # Explicit edit/commit seam; QTest coverage below.
    editor.editingFinished.emit()


def expire(case):
    case.now[0] = case.ui._pacing_wait.deadline_ns
    case.ui._simple_auto_timeout_slot()


class SimplePacingUITests(unittest.TestCase):
    close_ui = simple.LiveAutoUITests.close_ui
    prepare_board = simple.LiveAutoUITests.prepare_board

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        simple.LiveAutoUITests.setUp(self)
        self.now = [1_000_000_000]
        self.ui._pacing_clock_ns = lambda: self.now[0]

    def test_defaults_and_fixed_zero_do_not_load_profile(self):
        ui = self.ui
        self.assertEqual(ui._pacing_mode, FIXED)
        self.assertEqual(ui._pacing_rate, PacingRate())
        self.assertFalse(ui.pacing_rate_edit.isEnabled())
        self.assertTrue(ui.pacing_cps_edit.isEnabled())
        self.assertEqual(ui.pacing_cps_edit.text(), '5')
        self.assertEqual(ui.simple_auto_interval_spin.value(), 200)
        self.assertFalse(ui.simple_auto_checkbox.isChecked())
        self.assertFalse(ui.allow_guess_checkbox.isChecked())
        with patch('ui_manager.load_timing_table', side_effect=AssertionError('fixed profile')):
            ui.simple_auto_interval_spin.setValue(0)
            self.assertEqual(ui.pacing_cps_edit.text(), '최대')
            ui.simple_auto_checkbox.setChecked(True)
            self.assertIsNone(ui._pacing_wait)
            self.assertEqual(ui._simple_auto_timer.interval(), 0)
            with patch('core_engine.random.sample', return_value=[(1, 1)]):
                ui._simple_auto_timeout_slot()
        self.assertEqual(ui.live_auto_totals['auto_inputs'], 1)

    def test_editor_commit_exact_bounds_and_no_rounding_feedback(self):
        ui = self.ui
        mode(ui)
        edit(ui, '0.50402')  # Same exact rate, now entered directly in Model C.
        self.assertEqual(ui._pacing_rate.rate, Fraction('0.50402'))
        self.assertEqual(ui.pacing_rate_edit.text(), '0.50402')
        with patch.object(ui, '_restart_pacing_pending') as restart:
            for _ in range(10):
                ui.pacing_rate_edit.editingFinished.emit()
                ui.pacing_cps_edit.editingFinished.emit()
            ui.pacing_rate_edit.setText('3')  # Programmatic display is not a commit.
            ui.pacing_rate_edit.editingFinished.emit()
            restart.assert_not_called()
        self.assertEqual(ui._pacing_rate.rate, Fraction('0.50402'))
        for value, cps, expected in (('0.05', False, Fraction(1, 20)),
                                     ('8', False, Fraction(8)),
                                     ('1/20', False, Fraction(1, 20)),
                                     ('1/3', False, Fraction(1, 3))):
            with self.subTest(value=value, cps=cps):
                edit(ui, value, cps)
                self.assertEqual(ui._pacing_rate.rate, expected)
                old = ui._pacing_rate
                ui.pacing_cps_edit.editingFinished.emit()
                self.assertIs(ui._pacing_rate, old)
        self.assertIn('≈', ui.pacing_rate_edit.toolTip())
        self.assertFalse(ui.pacing_cps_edit.isEnabled())
        self.assertEqual(ui.pacing_cps_edit.text(), '—')
        for cps in (False, True):
            for value in ('0', '-1', 'NaN', 'inf', '1e9999999', '0.0001', '100'):
                with self.subTest(cps=cps, invalid=value):
                    old = ui._pacing_rate
                    edit(ui, value, cps)
                    self.assertIs(ui._pacing_rate, old)

    def test_keyboard_commit_is_once_and_enter_never_resets_game(self):
        ui = self.ui
        ui.show()
        ui.activateWindow()
        ui.pacing_cps_edit.setFocus()
        self.app.processEvents()
        changed = QSignalSpy(ui.simple_auto_interval_spin.valueChanged)
        with patch.object(ui, 'on_reset', side_effect=AssertionError('editor reset')), \
                patch.object(ui, '_restart_pacing_pending', wraps=ui._restart_pacing_pending) as restart:
            QTest.keyClick(ui.pacing_cps_edit, Qt.Key_A, Qt.ControlModifier)
            QTest.keyClicks(ui.pacing_cps_edit, '4')
            self.assertEqual(ui._pacing_rate, PacingRate())
            self.assertEqual(ui.simple_auto_interval_spin.value(), 200)
            QTest.keyClick(ui.pacing_cps_edit, Qt.Key_Return)
            self.assertEqual(ui.simple_auto_interval_spin.value(), 250)
            QTest.keyClick(ui.pacing_cps_edit, Qt.Key_Return)
            QTest.keyClick(ui.pacing_cps_edit, Qt.Key_Space)
            QTest.keyClick(ui.pacing_cps_edit, Qt.Key_Return)
            self.assertEqual(len(changed), 0)  # CPS sync does not emit an ms edit.
            restart.assert_not_called()
            mode(ui)
            restart.reset_mock()
            ui.pacing_rate_edit.setFocus()
            QTest.keyClick(ui.pacing_rate_edit, Qt.Key_A, Qt.ControlModifier)
            QTest.keyClicks(ui.pacing_rate_edit, '0.5')
            QTest.keyClick(ui.pacing_rate_edit, Qt.Key_Return)
            QTest.keyClick(ui.pacing_rate_edit, Qt.Key_Return)
            restart.assert_called_once()
            self.assertEqual(ui._pacing_rate.rate, Fraction(1, 2))
        self.assertEqual(ui._live_action_count, 0)

    def test_fixed_cps_conversion_rounding_maximum_and_invalid_reversion(self):
        ui = self.ui
        for requested, interval, text in (('4', 250, '4'), ('2', 500, '2'),
                ('10', 100, '10'), ('8', 125, '8'), ('0.5', 2000, '0.5'),
                ('1000', 1, '1000'), ('3', Fraction('333.333'), '3'),
                ('2000/667', Fraction('333.5'), '2.998501')):
            with self.subTest(requested=requested):
                edit(ui, requested, True)
                self.assertEqual(ui.simple_auto_interval_spin.value(), interval)
                self.assertEqual(ui.pacing_cps_edit.text(), text)
                raw = Fraction(1000000000, 1) / Fraction(requested)
                ns = -(-raw.numerator // raw.denominator)
                self.assertEqual(ui._fixed_period.period_ns, ns)
                self.assertEqual(ui._simple_auto_timer.interval(), (ns + 999999)//1000000)
        edit(ui, '3', True)
        self.assertEqual(ui.pacing_cps_edit.text(), '3')
        self.assertEqual(ui._fixed_period.period_ns, 333333334)
        self.assertIn('≈', ui.simple_auto_interval_spin.toolTip())
        for interval in (0, 333):
            ui.simple_auto_interval_spin.setValue(interval)
            expected = '최대' if interval == 0 else '3.003003'
            changed = QSignalSpy(ui.simple_auto_interval_spin.valueChanged)
            for invalid in ('0', '-1', '', 'NaN', 'Inf', '0.49999', '1000.00001'):
                with self.subTest(interval=interval, invalid=invalid):
                    edit(ui, invalid, True)
                    self.assertEqual(ui.simple_auto_interval_spin.value(), interval)
                    self.assertEqual(ui.pacing_cps_edit.text(), expected)
            self.assertEqual(len(changed), 0)
        ui.simple_auto_interval_spin.setValue(0)
        edit(ui, '4', True)
        self.assertEqual(ui.simple_auto_interval_spin.value(), 250)

    def test_fixed_cps_and_ms_share_existing_timer_and_pending(self):
        ui = self.ui
        ui.simple_auto_checkbox.setChecked(True)
        timer, result, slot = ui._simple_auto_timer, ui._analysis_result, ui._simple_auto_timeout_slot
        nonce = ui._v1_timer_nonce
        with patch('ui_manager.analyze_position', side_effect=AssertionError('extra decision')), \
                patch.object(timer, 'setInterval', wraps=timer.setInterval) as set_interval, \
                patch.object(ui, '_restart_pacing_pending') as model_restart:
            edit(ui, '4', True)
            set_interval.assert_called_once_with(250)
            model_restart.assert_not_called()
            self.assertIs(ui._simple_auto_timer, timer)
            self.assertIs(ui._analysis_result, result)
            self.assertIsNot(ui._simple_auto_timeout_slot, slot)
            self.assertGreater(ui._v1_timer_nonce, nonce)
            slot()  # A callback queued before the explicit change is revoked.
            self.assertEqual(ui._fixed_cadence.deadline_ns, self.now[0] + 250000000)
            self.assertTrue(timer.isActive())
            self.assertTrue(timer.isSingleShot())
            self.assertIsNone(ui._pacing_wait)
            self.assertEqual(ui._live_action_count, 0)
            set_interval.reset_mock()
            ui.simple_auto_interval_spin.setValue(100)
            self.assertEqual(ui.pacing_cps_edit.text(), '10')
            ui.simple_auto_interval_spin.setValue(250)
            self.assertEqual(ui.pacing_cps_edit.text(), '4')
            self.assertEqual(set_interval.call_args_list[-1].args, (250,))
        root = os.environ.get('PACING_RUN_ROOT')
        if root:
            (Path(root)/'FIXED_CPS_CONTROL.json').write_text(json.dumps(dict(
                cps_request=4, applied_interval_ms=250, timer_interval_ms=timer.interval(),
                same_timer=True, single_shot=timer.isSingleShot(), same_pending=True,
                existing_set_interval_calls_for_cps=1, new_model_restart_calls=0,
                input_count=ui._live_action_count)), encoding='utf-8')
        mode(ui)
        edit(ui, '0.5')
        wait, rate, nonce = ui._pacing_wait, ui._pacing_rate, ui._v1_timer_nonce
        edit(ui, '8', True)  # Disabled Model C CPS cannot alter either setting.
        self.assertIs(ui._pacing_rate, rate)
        self.assertIs(ui._pacing_wait, wait)
        self.assertEqual(ui._v1_timer_nonce, nonce)
        self.assertEqual(ui.simple_auto_interval_spin.value(), 250)
        self.assertEqual(ui.pacing_cps_edit.text(), '—')
        mode(ui, FIXED)
        self.assertEqual(ui.pacing_cps_edit.text(), '4')
        self.assertEqual(timer.interval(), 250)

    def test_fixed_ms_cps_roundtrips_and_unchanged_edits_do_not_restart(self):
        ui = self.ui
        for interval in (0, 1, 2, 3, 16, 125, 180, 250, 333, 667, 1999, 2000):
            with self.subTest(interval=interval):
                ui.simple_auto_interval_spin.setValue(interval)
                changed = QSignalSpy(ui.simple_auto_interval_spin.valueChanged)
                for _ in range(25):
                    ui.pacing_cps_edit.editingFinished.emit()
                    edit(ui, ui.pacing_cps_edit.text(), True)
                    self.assertEqual(ui.simple_auto_interval_spin.value(), interval)
                self.assertEqual(len(changed), 0)
        ui.pacing_cps_edit.setText('4')  # Programmatic text is not a user commit.
        ui.pacing_cps_edit.editingFinished.emit()
        self.assertEqual(ui.simple_auto_interval_spin.value(), 2000)
        ui._sync_pacing_editors()
        self.assertEqual(ui.pacing_cps_edit.text(), '0.5')

    def test_fixed_cps_guess_pause_and_manual_cancel_late_callback(self):
        ui = self.ui
        ui.show()
        ui.activateWindow()
        self.app.processEvents()
        self.engine.reset_with_mines(3, 3, 1, {(1, 1)})
        ui.simple_auto_checkbox.setChecked(True)
        self.assertFalse(ui._simple_auto_pending)
        edit(ui, '4', True)
        ui.allow_guess_checkbox.setChecked(True)
        self.assertTrue(ui._simple_auto_pending)
        old = ui._simple_auto_timeout_slot
        ui.allow_guess_checkbox.setChecked(False)
        edit(ui, '2', True)
        old()
        self.assertFalse(ui._simple_auto_pending)
        self.assertEqual(ui._live_action_count, 0)
        ui.allow_guess_checkbox.setChecked(True)
        ui.simple_auto_checkbox.setChecked(False)
        edit(ui, '8', True)
        old()
        self.assertFalse(ui._simple_auto_timer.isActive())
        ui.simple_auto_checkbox.setChecked(True)
        self.assertEqual(ui._simple_auto_timer.interval(), 125)
        old = ui._simple_auto_timeout_slot
        QTest.mousePress(ui._buttons[(0, 0)], Qt.LeftButton)
        old()
        self.assertFalse(ui.simple_auto_checkbox.isChecked())
        self.assertFalse(ui.allow_guess_checkbox.isChecked())
        self.assertEqual(ui._live_action_count, 0)
        QTest.mouseRelease(ui._buttons[(0, 0)], Qt.LeftButton)
        self.assertEqual(ui._live_action_count, 1)
        self.assertEqual(ui.live_auto_totals['auto_inputs'], 0)

    def test_early_timeout_and_rate_mode_changes_keep_original_move(self):
        ui = self.ui
        mode(ui)
        ui.simple_auto_checkbox.setChecked(True)
        result = ui._analysis_result
        old_slot = ui._simple_auto_timeout_slot
        with patch('ui_manager.analyze_position', side_effect=AssertionError('new decision')):
            for rate in ('1', '0.5', '0.25'):
                edit(ui, rate)
                wait = ui._pacing_wait
                self.assertEqual(wait.exact_us, Fraction(126005) / Fraction(rate))
                self.now[0] = wait.deadline_ns - 1
                nonce = ui._v1_timer_nonce
                ui._simple_auto_timeout_slot()
                self.assertEqual(ui._simple_auto_timer.interval(), 1)
                self.assertEqual(ui._v1_timer_nonce, nonce)
                self.assertIs(ui._analysis_result, result)
                self.assertEqual(ui._live_action_count, 0)
            wait, nonce = ui._pacing_wait, ui._v1_timer_nonce
            ui.simple_auto_interval_spin.setValue(700)
            self.assertIs(ui._pacing_wait, wait)
            self.assertEqual(ui._v1_timer_nonce, nonce)
            mode(ui, FIXED)
            self.assertIsNone(ui._pacing_wait)
            self.assertEqual(ui._simple_auto_timer.interval(), 200)  # Hidden ms edit is blocked.
            mode(ui)
            self.assertEqual(ui._pacing_wait.rate.rate, Fraction(1, 4))
            old_slot()
            self.assertEqual(ui._live_action_count, 0)
            ui.simple_auto_checkbox.setChecked(False)
            self.assertIsNone(ui._pacing_wait)
            self.now[0] += 1_000_000_000
            ui.simple_auto_checkbox.setChecked(True)
            self.assertIs(ui._analysis_result, result)
            self.assertEqual(ui._pacing_wait.started_ns, self.now[0])
        with patch('core_engine.random.sample', return_value=[(1, 1)]):
            expire(self)
        self.assertEqual(ui.live_auto_totals['auto_inputs'], 1)
        self.assertEqual(ui.live_auto_totals['modeled_us'], 0)
        self.assertEqual(ui._v1_cursor, (result.move.x, result.move.y))
        self.assertIsNone(ui._mouse_trace_recorder.snapshot())

    def test_simple_cost_uses_actual_cursor_for_normal_guess_and_preparation(self):
        for scenario in ('normal', 'guess', 'preparation'):
            with self.subTest(scenario=scenario):
                ui = self.ui
                ui.analysis_checkbox.setChecked(False)
                ui.on_reset()
                self.engine.reset_with_mines(3, 3, 1, {(1, 1)})
                if scenario == 'normal':
                    ui.on_left_click(0, 0)
                elif scenario == 'preparation':
                    ui.on_right_click(2, 2)
                mode(ui)
                edit(ui, '0.5')
                ui.simple_auto_checkbox.setChecked(True)
                if scenario != 'preparation':
                    ui.allow_guess_checkbox.setChecked(True)
                move = ui._analysis_result.move
                cost = action_cost(load_timing_table(), ui._v1_cursor, (move.x, move.y))
                self.assertEqual(ui._pacing_wait.modeled_action_us, cost)
                self.assertEqual(ui._pacing_wait.exact_us, cost * 2)
                self.assertTrue(ui.auto_cursor_overlay.isHidden())
                self.assertIsNone(ui.auto_cursor_overlay._reservation)
                if scenario == 'preparation':
                    self.assertEqual(move.action, Action.FLAG)
                    expire(self)
                    self.assertEqual(ui.live_action_records[-1]['semantic_input'], 'UNFLAG')
                    self.assertEqual(ui.live_action_records[-1]['modeled_action_us'], cost)

    def test_guess_off_cancels_and_late_callback_cannot_input(self):
        self.engine.reset_with_mines(3, 3, 1, {(1, 1)})
        ui = self.ui
        mode(ui)
        ui.simple_auto_checkbox.setChecked(True)
        self.assertIsNone(ui._pacing_wait)
        ui.allow_guess_checkbox.setChecked(True)
        slot = ui._simple_auto_timeout_slot
        self.now[0] = ui._pacing_wait.deadline_ns
        ui.allow_guess_checkbox.setChecked(False)
        slot()
        self.assertEqual(ui._live_action_count, 0)
        self.assertIsNone(ui._pacing_wait)

    def test_large_custom_falls_back_without_loading_or_blocking_fixed_auto(self):
        ui = self.ui
        mode(ui)
        edit(ui, '0.5')
        for width, height in ((31, 16), (30, 17)):
            with self.subTest(width=width, height=height):
                ui._rebuild_game(width, height, 10)
                self.assertFalse(ui._model_c_pacing_active())
                self.assertEqual(ui.pacing_mode_combo.currentData(), FIXED)
                self.assertFalse(ui.pacing_mode_combo.model().item(1).isEnabled())
                self.assertTrue(ui.simple_auto_interval_spin.isEnabled())
                self.assertIn('30×16', ui.pacing_status_label.text())
                with patch('ui_manager.load_timing_table', side_effect=AssertionError('outside table')):
                    ui.simple_auto_interval_spin.setValue(0)
                    ui.simple_auto_checkbox.setChecked(True)
                    self.assertTrue(ui._simple_auto_pending)
                    self.assertEqual(ui._simple_auto_timer.interval(), 0)
                ui.simple_auto_checkbox.setChecked(False)
        ui._rebuild_game(30, 16, 99)
        self.assertTrue(ui._model_c_pacing_active())
        self.assertEqual(ui._pacing_rate.rate, Fraction(1, 2))

    def test_profile_failure_stops_in_existing_boundary(self):
        mode(self.ui)
        with patch('ui_manager.load_timing_table', side_effect=ValueError('Frozen profile mismatch')):
            self.ui.simple_auto_checkbox.setChecked(True)
        self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
        self.assertEqual(self.ui._live_action_count, 0)
        self.assertIsNone(self.ui._pacing_wait)
        self.assertIn('Frozen profile mismatch', self.ui.analysis_status_label.text())

    def test_bad_lookup_cost_and_terminal_leave_no_reservation(self):
        mode(self.ui)
        with patch('ui_manager.action_cost', return_value=0):
            self.ui.simple_auto_checkbox.setChecked(True)
        self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
        self.assertIsNone(self.ui._pacing_wait)
        self.ui._rebuild_game(2, 1, 1)
        self.engine.reset_with_mines(2, 1, 1, {(1, 0)})
        self.ui.on_analyze_current()  # Synthetic placement must refresh the first-click view.
        self.ui.simple_auto_checkbox.setChecked(True)
        self.ui.allow_guess_checkbox.setChecked(True)
        expire(self)
        self.assertEqual(self.engine.status.name, 'WON')
        self.assertIsNone(self.ui._pacing_wait)
        self.assertIsNone(self.ui._certainty_frame)
        self.assertIsNone(self.ui.auto_cursor_overlay._reservation)

    def test_live_controls_geometry_and_frozen_reference(self):
        self.assertEqual(load_timing_table()[1][0], 126005)
        mode(self.ui)
        edit(self.ui, '0.50402')
        self.ui.show()
        self.app.processEvents()
        self.assertFalse(self.ui.pacing_fixed_group.isVisible())
        controls = (self.ui.pacing_rate_label, self.ui.pacing_rate_edit)
        for left, right in zip(controls, controls[1:]):
            self.assertLess(left.geometry().right(), right.geometry().left())
        self.assertGreater(self.ui.scroll_area.geometry().top(), self.ui.pacing_bar.geometry().bottom())
        root = os.environ.get('PACING_RUN_ROOT')
        if root:
            self.assertTrue(self.ui.grab().save(str(Path(root)/'pacing-ui.png')))

    def test_reset_policy_replay_keep_settings_and_disable_live_editing(self):
        ui = self.ui
        ui.simple_auto_interval_spin.setValue(180)  # A user value, not the new-window default.
        mode(ui)
        edit(ui, '0.50402')
        setting = ui._pacing_rate
        ui.on_reset()
        ui.live_policy_combo.setCurrentIndex(ui.live_policy_combo.findData(POLICY_V1))
        ui.live_policy_combo.setCurrentIndex(ui.live_policy_combo.findData(POLICY_SIMPLE))
        ui._enter_replay_mode(ReplayPlayer(ReplayData(ReplayBoard(3, 3, 1, {(1, 1)}), (
            ReplayEvent(1, 0, 0, 'OPEN'),))))
        for editor in (ui.pacing_rate_edit, ui.pacing_cps_edit, ui.pacing_mode_combo,
                       ui.simple_auto_interval_spin):
            self.assertFalse(editor.isEnabled())
        edit(ui, '2')
        mode(ui, FIXED)
        self.assertIs(ui._pacing_rate, setting)
        self.assertEqual(ui._pacing_mode, MODEL_C)
        ui._exit_replay_mode()
        self.assertIs(ui._pacing_rate, setting)
        self.assertTrue(ui.pacing_rate_edit.isEnabled())
        self.assertEqual(ui.simple_auto_interval_spin.value(), 180)
        self.assertEqual(ui.pacing_cps_edit.text(), '—')
        mode(ui, FIXED)
        self.assertEqual(ui.pacing_cps_edit.text(), '5.555556')
        self.assertIs(ui._pacing_rate, setting)


class FamilyPacingUITests(unittest.TestCase):
    close_ui = display.LiveDisplayTests.close_ui
    prepare = display.LiveDisplayTests.prepare
    certainty = display.LiveDisplayTests.certainty

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        display.LiveDisplayTests.setUp(self)
        self.now = [2_000_000_000]
        self.ui._pacing_clock_ns = lambda: self.now[0]
        self.ui.auto_cursor_overlay._clock = lambda: self.now[0] / 1_000_000_000

    def test_fixed_cps_pending_validate_ack_and_manual_follow_interval_path(self):
        for policy in (POLICY_V1, POLICY_K, POLICY_K_LC0, POLICY_K_LC1):
            with self.subTest(policy=policy):
                self.prepare(policy)
                ui = self.ui
                mode(ui, FIXED)
                proposal, colors = ui._v1_pending, self.certainty()
                requests = len(self.job.requests)
                with patch.object(ui, '_schedule_v1_step', wraps=ui._schedule_v1_step) as schedule:
                    edit(ui, '4', True)
                    schedule.assert_called_once()
                if self.job.state == 'validating' and ui._k_validation_nonce is None:
                    self.job.deliver_admission()
                self.assertIs(ui._v1_pending, proposal)
                self.assertEqual(len(self.job.requests), requests)
                self.assertEqual(self.certainty(), colors)
                self.assertEqual(ui._simple_auto_timer.interval(), 250)
                self.assertEqual(ui.auto_cursor_overlay._motion[3], 0.25)
                self.assertIsNone(ui._pacing_wait)
                old = ui._simple_auto_timeout_slot
                ui.simple_auto_checkbox.setChecked(False)
                edit(ui, '2', True)
                old()
                self.assertEqual(ui._live_action_count, 1)
                ui.simple_auto_checkbox.setChecked(True)
                self.assertEqual(ui._simple_auto_timer.interval(), 500)
                self.now[0] = ui._fixed_cadence.deadline_ns
                ui._simple_auto_timeout_slot()
                if policy != POLICY_V1:
                    self.assertEqual(self.job.state, 'validating')
                    old_nonce = ui._k_validation_nonce
                    edit(ui, '10', True)
                    self.assertIsNone(ui._k_validation_nonce)
                    self.job.deliver_admission()
                    self.assertEqual(ui._live_action_count, 1)
                    self.assertIs(ui._v1_pending, proposal)
                    self.assertEqual(ui._simple_auto_timer.interval(), 100)
                    self.now[0] = ui._fixed_cadence.deadline_ns
                    ui._simple_auto_timeout_slot()
                    self.assertNotEqual(ui._k_validation_nonce, old_nonce)
                    self.job.deliver_admission()
                self.assertEqual(ui._live_action_count, 2)
                self.assertEqual(ui.live_action_records[-1]['modeled_action_us'], proposal.modeled_action_us)
                ui.simple_auto_checkbox.setChecked(False)
                edit(ui, '8', True)  # ACK outstanding: only the stored fixed interval changes.
                self.assertEqual(len(self.job.requests), requests)
                self.assertEqual(ui._live_action_count, 2)
                if policy == POLICY_K_LC1:
                    QTest.mousePress(ui._buttons[(5, 0)], Qt.RightButton)
                    QTest.mouseRelease(ui._buttons[(5, 0)], Qt.RightButton)
                    self.assertFalse(ui.simple_auto_checkbox.isChecked())
                    self.assertFalse(ui.allow_guess_checkbox.isChecked())
                self.job.deliver_ack()
                if policy == POLICY_K_LC1:
                    self.job.complete_cancel()
                self.assertEqual(ui.simple_auto_interval_spin.value(), 125)
                self.assertIsNone(ui._live_first_failure)

    def test_all_policy_original_cost_choice_cursor_and_once_input(self):
        for policy in (POLICY_V1, POLICY_K, POLICY_K_LC0, POLICY_K_LC1):
            for rate in ('1', '0.5', '0.25'):
                with self.subTest(policy=policy, rate=rate):
                    self.prepare(policy)
                    ui = self.ui
                    mode(ui)
                    edit(ui, rate)
                    p = ui._v1_pending
                    requests = len(self.job.requests)
                    colors = self.certainty()
                    wait = ui._pacing_wait
                    self.assertEqual(wait.modeled_action_us, p.modeled_action_us)
                    self.assertEqual(wait.exact_us, Fraction(p.modeled_action_us) / Fraction(rate))
                    self.assertEqual(ui.auto_cursor_overlay._motion[3], wait.delay_ms / 1000)
                    state = (ui._v1_timer_nonce, ui._pacing_wait, ui.auto_cursor_overlay._generation)
                    for enabled in (False, True, False, True):
                        ui.auto_cursor_checkbox.setChecked(enabled)
                    self.assertEqual(state, (ui._v1_timer_nonce, ui._pacing_wait, ui.auto_cursor_overlay._generation))
                    self.assertEqual(self.certainty(), colors)
                    self.assertEqual(len(self.job.requests), requests)
                    self.now[0] = wait.deadline_ns - 1
                    ui._simple_auto_timeout_slot()
                    self.assertEqual(ui._live_action_count, 1)
                    self.assertIs(ui._v1_pending, p)
                    expire(self)
                    if policy != POLICY_V1:
                        self.assertEqual(self.job.state, 'validating')
                        self.job.deliver_admission()
                    ui.simple_auto_checkbox.setChecked(False)
                    self.job.deliver_ack()
                    self.assertEqual(ui._live_action_count, 2)
                    self.assertEqual(ui.live_auto_totals['modeled_us'], p.modeled_action_us)
                    self.assertEqual(ui.live_auto_totals['auto_inputs'], 1)
                    self.assertEqual(ui._v1_cursor, (p.x, p.y))
                    self.assertEqual(ui.live_action_records[-1]['modeled_action_us'], p.modeled_action_us)
                    self.assertTrue(self.certainty())

    def test_rate_change_during_validate_drains_old_permit_then_full_wait(self):
        for policy in (POLICY_K, POLICY_K_LC0, POLICY_K_LC1):
            with self.subTest(policy=policy):
                self.prepare(policy)
                ui = self.ui
                mode(ui)
                edit(ui, '1')
                p = ui._v1_pending
                old_slot = ui._simple_auto_timeout_slot
                expire(self)
                old_nonce = ui._k_validation_nonce
                edit(ui, '0.50402')
                self.assertIsNone(ui._k_validation_nonce)
                self.assertIsNone(ui._pacing_wait)
                self.assertFalse(ui._k_retired)
                self.job.deliver_admission()
                self.assertEqual(ui._live_action_count, 1)
                self.assertIs(ui._v1_pending, p)
                wait = ui._pacing_wait
                self.assertEqual(wait.started_ns, self.now[0])
                self.assertEqual(wait.rate, PacingRate('0.50402'))
                old_slot()
                self.assertIs(ui._pacing_wait, wait)
                expire(self)
                self.assertNotEqual(ui._k_validation_nonce, old_nonce)
                self.job.deliver_admission()
                self.assertEqual(ui._live_action_count, 2)
                self.assertFalse(ui._k_retired)

    def test_initial_inputs_and_guess_off_keep_the_same_cost_contract(self):
        for policy in (POLICY_V1, POLICY_K, POLICY_K_LC0, POLICY_K_LC1):
            with self.subTest(policy=policy):
                if self.job.active_run_id is not None:
                    self.ui._invalidate_v1_run('initial fixture')
                    self.job.complete_cancel()
                ui = self.ui
                ui.analysis_checkbox.setChecked(False)
                ui.live_policy_combo.setCurrentIndex(ui.live_policy_combo.findData(policy))
                ui.on_reset()
                mode(ui)
                edit(ui, '0.5')
                ui.simple_auto_checkbox.setChecked(True)
                self.job.compute()
                p = ui._v1_pending
                self.assertTrue(p.initial)
                self.assertFalse(ui.allow_guess_checkbox.isChecked())
                self.assertEqual(ui._pacing_wait.exact_us, p.modeled_action_us * 2)
                with patch('core_engine.random.sample', return_value=UI_MINES):
                    expire(self)
                    if policy != POLICY_V1:
                        self.job.deliver_admission()
                ui.simple_auto_checkbox.setChecked(False)
                self.job.deliver_ack()
                self.assertEqual(ui._live_action_count, 1)
                self.assertEqual(ui.live_auto_totals['modeled_us'], p.modeled_action_us)

    def test_flag_then_chord_use_each_proposals_cost(self):
        for policy in (POLICY_V1, POLICY_K):
            with self.subTest(policy=policy):
                self.prepare(policy)
                ui = self.ui
                mode(ui)
                edit(ui, '0.5')
                for expected in ('FLAG', 'CHORD'):
                    p = ui._v1_pending
                    self.assertEqual(p.action, expected)
                    self.assertEqual(ui._pacing_wait.exact_us, p.modeled_action_us * 2)
                    expire(self)
                    if policy != POLICY_V1:
                        self.job.deliver_admission()
                    ui.simple_auto_checkbox.setChecked(False)
                    self.job.deliver_ack()
                    if expected == 'FLAG':
                        ui.simple_auto_checkbox.setChecked(True)
                        self.job.compute()
                self.assertEqual(ui.live_auto_totals['auto_inputs'], 2)

    def test_ack_edit_manual_press_and_readopt_after_cleanup(self):
        self.prepare(POLICY_K_LC1)
        ui = self.ui
        mode(ui)
        expire(self)
        self.job.deliver_admission()
        edit(ui, '0.5')
        owner = self.job.active_run_id
        requests = len(self.job.requests)
        QTest.mousePress(ui._buttons[(5, 0)], Qt.RightButton)
        QTest.mouseRelease(ui._buttons[(5, 0)], Qt.RightButton)
        self.assertFalse(ui.simple_auto_checkbox.isChecked())
        self.assertFalse(ui.allow_guess_checkbox.isChecked())
        ui.simple_auto_checkbox.setChecked(True)
        self.assertEqual(len(self.job.requests), requests)
        self.job.deliver_ack()
        self.job.complete_cancel()
        ui.simple_auto_checkbox.setChecked(True)
        self.job.compute()
        if ui._v1_pending is None:
            self.job.compute()
        self.assertNotEqual(self.job.active_run_id, owner)
        self.assertEqual(ui._pacing_wait.rate.rate, Fraction(1, 2))
        self.assertIsNone(ui._live_first_failure)

    def test_ack_edits_and_pause_resume_do_not_issue_extra_request_or_input(self):
        for policy in (POLICY_V1, POLICY_K, POLICY_K_LC0, POLICY_K_LC1):
            with self.subTest(policy=policy):
                self.prepare(policy)
                ui = self.ui
                mode(ui)
                p = ui._v1_pending
                old = ui._simple_auto_timeout_slot
                ui.simple_auto_checkbox.setChecked(False)
                self.now[0] += 7_000_000_000
                old()
                ui.simple_auto_checkbox.setChecked(True)
                self.assertIs(ui._v1_pending, p)
                self.assertEqual(ui._pacing_wait.started_ns, self.now[0])
                expire(self)
                if policy != POLICY_V1:
                    self.job.deliver_admission()
                requests = len(self.job.requests)
                for value in ('0.25', '8', '0.5'):
                    edit(ui, value)
                self.assertIsNone(ui._pacing_wait)
                self.assertEqual(len(self.job.requests), requests)
                self.assertEqual(ui._live_action_count, 2)
                self.job.deliver_ack()
                self.job.compute()
                self.assertEqual(ui._pacing_wait.rate.rate, Fraction(1, 2))
                self.assertEqual(ui._pacing_wait.started_ns, self.now[0])

    def test_preparation_uses_original_proposal_cost_in_all_four_policies(self):
        for policy in (POLICY_V1, POLICY_K, POLICY_K_LC0, POLICY_K_LC1):
            with self.subTest(policy=policy):
                if self.job.active_run_id is not None:
                    self.ui._invalidate_v1_run('fixture change')
                    self.job.complete_cancel()
                ui = self.ui
                ui.analysis_checkbox.setChecked(False)
                ui.live_policy_combo.setCurrentIndex(ui.live_policy_combo.findData(policy))
                ui.on_reset()
                with patch('core_engine.random.sample', return_value=UI_MINES):
                    for x, y in ((0, 0), (0, 1), (1, 1), (2, 0), (2, 1)):
                        ui.on_left_click(x, y)
                    for x in (1, 3, 4):
                        ui.on_right_click(x, 0)
                mode(ui)
                edit(ui, '0.25')
                ui.simple_auto_checkbox.setChecked(True)
                self.job.compute()
                if policy != POLICY_V1:
                    self.job.compute()
                p = ui._v1_pending
                self.assertEqual((p.action, p.x, p.y), ('FLAG', 3, 0))
                self.assertEqual(ui._pacing_wait.exact_us, p.modeled_action_us * 4)
                expire(self)
                if policy != POLICY_V1:
                    self.job.deliver_admission()
                ui.simple_auto_checkbox.setChecked(False)
                self.job.deliver_ack()
                record = ui.live_action_records[-1]
                self.assertEqual(record['semantic_input'], 'UNFLAG')
                self.assertEqual(record['modeled_action_us'], p.modeled_action_us)

    def test_hard_boundaries_clear_pending_motion_colors_and_late_delivery(self):
        for boundary in ('manual', 'reset', 'policy', 'difficulty', 'replay', 'failure', 'close'):
            with self.subTest(boundary=boundary):
                case = type(self)()
                case.setUp()
                try:
                    case.prepare(POLICY_K_LC1)
                    ui = case.ui
                    mode(ui)
                    old = ui._simple_auto_timeout_slot
                    expire(case)
                    if boundary == 'manual':
                        QTest.mousePress(ui._buttons[(3, 3)], Qt.LeftButton)
                    elif boundary == 'reset':
                        ui.on_reset()
                    elif boundary == 'policy':
                        ui.live_policy_combo.setCurrentIndex(0)
                    elif boundary == 'difficulty':
                        ui.difficulty_combo.setCurrentIndex(1)
                    elif boundary == 'replay':
                        ui._enter_replay_mode(ReplayPlayer(ReplayData(ReplayBoard(2, 1, 1, {(1, 0)}), ())))
                    elif boundary == 'failure':
                        ui._fail_v1('pacing fixture failure')
                    else:
                        ui.close()
                    count = ui._live_action_count
                    old()
                    # A valid old permit is delivered only while the fake actor
                    # still owns its pending. Disposed actor callbacks are ignored.
                    if case.job.owner is not None and case.job.validation is not None:
                        ui._on_k_admitted(case.job.owner.validate(case.job.validation))
                    self.assertEqual(ui._live_action_count, count)
                    self.assertIsNone(ui._pacing_wait)
                    self.assertIsNone(ui.auto_cursor_overlay._reservation)
                    self.assertIsNone(ui._certainty_frame)
                    if boundary == 'manual':
                        self.assertFalse(ui.simple_auto_checkbox.isChecked())
                        self.assertFalse(ui.allow_guess_checkbox.isChecked())
                        QTest.mouseRelease(ui._buttons[(3, 3)], Qt.LeftButton)
                finally:
                    case.doCleanups()
