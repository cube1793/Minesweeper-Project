"""Fake-clock UI cadence oracle. Real IPC is separately opt-in."""
import unittest
from unittest.mock import patch

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from core_engine import Action
from live_policy import POLICY_V1, POLICY_K, POLICY_K_LC0, POLICY_K_LC1
from live_pacing import MODEL_C
from tests import test_live_k_ui as base
from tests.test_live_k_lc0_ui import FamilyFakeJob
from tests.test_live_pacing_ui import edit, mode
from tests import test_live_auto as simple
from replay_model import ReplayBoard, ReplayData
from replay_player import ReplayPlayer


class FixedCadenceUITests(unittest.TestCase):
    close_ui = base.LiveKUITests.close_ui

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        with patch.object(base, 'KUIFakeJob', FamilyFakeJob):
            base.LiveKUITests.setUp(self)
        self.now = [1000000000]
        self.ui._pacing_clock_ns = lambda: self.now[0]
        self.ui.auto_cursor_overlay._clock = lambda: self.now[0] / 1000000000
        self.steps = []
        original = self.engine.step
        def step(*args):
            self.steps.append((self.now[0], args))
            return original(*args)
        watched = patch.object(self.engine, 'step', side_effect=step)
        watched.start()
        self.addCleanup(watched.stop)

    def advance(self, milliseconds):
        self.now[0] += milliseconds * 1000000

    def arm(self, policy=POLICY_K, prepare_ms=80):
        self.ui.live_policy_combo.setCurrentIndex(self.ui.live_policy_combo.findData(policy))
        self.ui.on_reset()
        self.ui.simple_auto_checkbox.setChecked(True)
        self.ui.allow_guess_checkbox.setChecked(True)
        self.start_ns = self.now[0]
        self.advance(prepare_ms)
        self.job.compute()
        return self.job.pending

    def due(self):
        self.ui._simple_auto_timeout_slot()

    def fast(self, policy):
        p = self.arm(policy)
        expected = self.start_ns + 200000000
        self.assertEqual(self.ui._fixed_cadence.deadline_ns, expected)
        self.assertEqual(self.ui._simple_auto_timer.interval(), 120)
        if policy != POLICY_V1:
            self.assertEqual(self.job.state, 'validating')
            self.advance(40)
            permit = self.job.deliver_admission()
            self.assertIs(self.ui._k_deferred_permit, permit)
            self.assertEqual(self.job.applied, [])
        self.now[0] = expected - 1
        self.due()
        self.assertEqual(self.steps, [])
        self.assertEqual(self.ui._simple_auto_timer.interval(), 1)
        self.now[0] = expected
        old = self.ui._simple_auto_timeout_slot
        self.due()
        old()
        self.assertEqual(len(self.steps), 1)
        self.assertEqual(self.steps[0][0], expected)
        self.assertEqual(self.ui._fixed_cadence.deadline_ns, expected + 200000000)
        self.assertEqual(self.ui.live_action_records[-1]['modeled_action_us'], p.modeled_action_us)
        self.advance(40)
        self.job.deliver_ack()
        self.advance(30)
        self.job.compute()
        self.assertEqual(self.ui._simple_auto_timer.interval(), 130)
        self.assertIsNone(self.ui._live_first_failure)

    def test_v1_compute_and_ack_fit_in_the_same_period(self):
        self.fast(POLICY_V1)

    def test_k_p0_validate_early_and_hold_without_consuming(self):
        self.fast(POLICY_K)

    def test_k_lc0_validate_early_and_hold_without_consuming(self):
        self.fast(POLICY_K_LC0)

    def test_k_lc1_validate_early_and_hold_without_consuming(self):
        self.fast(POLICY_K_LC1)

    def test_late_permit_does_not_add_wait_or_catch_up(self):
        self.arm(prepare_ms=180)
        self.advance(20)
        self.due()
        self.assertEqual(self.steps, [])
        self.advance(170)
        actual = self.now[0]
        self.job.deliver_admission()
        self.assertEqual([t for t, _ in self.steps], [actual])
        self.assertEqual(self.ui._fixed_cadence.deadline_ns, actual + 200000000)
        self.job.deliver_ack()
        self.job.compute()
        self.assertEqual(self.ui._simple_auto_timer.interval(), 200)

    def test_late_proposal_uses_zero_remaining_wait(self):
        self.arm(POLICY_V1, prepare_ms=370)
        self.assertEqual(self.ui._simple_auto_timer.interval(), 0)
        self.due()
        self.assertEqual(len(self.steps), 1)
        self.assertEqual(self.ui._fixed_cadence.deadline_ns, self.now[0] + 200000000)

    def test_pause_validate_drain_and_rate_change_restart_whole_period(self):
        p = self.arm(prepare_ms=20)
        old_slot = self.ui._simple_auto_timeout_slot
        self.ui.simple_auto_checkbox.setChecked(False)
        self.advance(30)
        stale = self.job.deliver_admission()
        self.assertEqual(self.steps, [])
        self.assertIs(self.ui._v1_pending, p)
        self.ui.simple_auto_checkbox.setChecked(True)
        self.assertEqual(self.ui._fixed_cadence.deadline_ns, self.now[0] + 200000000)
        self.advance(20)
        self.job.deliver_admission()
        old_nonce = self.ui._k_validation_nonce
        edit(self.ui, '4', True)
        deadline = self.now[0] + 250000000
        self.assertEqual(self.ui._fixed_cadence.deadline_ns, deadline)
        self.assertNotEqual(self.ui._k_validation_nonce, old_nonce)
        old_slot()
        self.ui._on_k_admitted(stale)
        self.job.deliver_admission()
        self.assertEqual(self.steps, [])
        self.now[0] = deadline
        self.due()
        self.assertEqual(len(self.steps), 1)
        self.assertIsNone(self.ui._live_first_failure)

    def test_same_edit_and_display_toggles_preserve_deadline_nonce_and_permit(self):
        self.arm()
        permit = self.job.deliver_admission()
        before = (self.ui._fixed_cadence, self.ui._k_validation_nonce,
                  self.ui._v1_timer_reservation, len(self.job.validations))
        self.advance(15)
        edit(self.ui, '5', True)
        for value in (False, True, False):
            self.ui.auto_cursor_checkbox.setChecked(value)
            self.ui.probability_checkbox.setChecked(value)
        self.assertEqual(before, (self.ui._fixed_cadence, self.ui._k_validation_nonce,
                         self.ui._v1_timer_reservation, len(self.job.validations)))
        self.assertIs(self.ui._k_deferred_permit, permit)
        self.assertEqual(self.steps, [])

    def test_zero_is_one_current_input_and_model_c_still_waits_before_validate(self):
        self.ui.simple_auto_interval_spin.setValue(0)
        self.arm(prepare_ms=20)
        self.assertEqual(self.ui._simple_auto_timer.interval(), 0)
        self.job.deliver_admission()
        self.assertEqual(len(self.steps), 1)
        self.job.deliver_ack()
        mode(self.ui, MODEL_C)
        self.job.compute()
        self.assertIsNotNone(self.ui._pacing_wait)
        self.assertEqual(self.job.state, 'pending')
        self.assertIsNone(self.ui._fixed_cadence)

    def cancel_held(self, action):
        self.arm()
        permit = self.job.deliver_admission()
        old = self.ui._simple_auto_timeout_slot
        action()
        count = len(self.steps)
        self.advance(1000)
        old()
        self.ui._on_k_admitted(permit)
        self.assertEqual(len(self.steps), count)
        self.assertIsNone(self.ui._fixed_cadence)
        self.assertIsNone(self.ui._k_deferred_permit)
        self.assertIsNone(self.ui.auto_cursor_overlay._reservation)

    def test_held_permit_cannot_survive_same_shaped_reset(self):
        self.cancel_held(self.ui.on_reset)

    def test_held_permit_cannot_survive_policy_change(self):
        self.cancel_held(lambda: self.ui.live_policy_combo.setCurrentIndex(0))

    def test_held_permit_cannot_survive_replay(self):
        self.cancel_held(lambda: self.ui._enter_replay_mode(
            ReplayPlayer(ReplayData(ReplayBoard(2, 1, 1, {(1, 0)}), ()))))

    def test_held_permit_cannot_survive_close(self):
        self.cancel_held(self.ui.close)

    def test_first_manual_press_revokes_held_permit_before_release(self):
        self.ui.show()
        self.app.processEvents()
        self.arm()
        permit = self.job.deliver_admission()
        old = self.ui._simple_auto_timeout_slot
        cell = self.ui._buttons[(3, 3)]
        QTest.mousePress(cell, Qt.LeftButton)
        self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
        self.assertEqual(self.steps, [])
        self.advance(500)
        old()
        self.ui._on_k_admitted(permit)
        self.assertEqual(self.steps, [])
        QTest.mouseRelease(cell, Qt.LeftButton)
        self.assertEqual(len(self.steps), 1)
        self.assertIsNone(self.ui._fixed_cadence)
        self.assertIsNone(self.ui._live_first_failure)

    def test_guess_off_revokes_early_validation_and_never_catches_up(self):
        self.arm()
        self.job.deliver_admission()
        self.now[0] = self.ui._fixed_cadence.deadline_ns
        self.due()
        self.job.deliver_ack()
        self.job.compute()
        self.assertTrue(self.job.pending.is_guess)
        old = self.ui._simple_auto_timeout_slot
        self.ui.allow_guess_checkbox.setChecked(False)
        self.job.deliver_admission()
        self.advance(1000)
        old()
        self.assertEqual(len(self.steps), 1)
        self.ui.allow_guess_checkbox.setChecked(True)
        self.job.deliver_admission()
        self.assertEqual(len(self.steps), 2)
        self.assertEqual(self.ui._fixed_cadence.deadline_ns, self.now[0] + 200000000)

    def test_delayed_ack_and_edit_keep_new_period_without_an_extra_wait(self):
        self.arm()
        self.job.deliver_admission()
        self.now[0] = self.ui._fixed_cadence.deadline_ns
        self.due()
        self.advance(50)
        edit(self.ui, '10', True)
        anchor = self.now[0]
        self.assertEqual(self.ui._fixed_cadence.deadline_ns, anchor + 100000000)
        self.advance(300)
        self.job.deliver_ack()
        self.job.compute()
        self.assertEqual(self.ui._simple_auto_timer.interval(), 0)
        self.job.deliver_admission()
        self.assertEqual(len(self.steps), 2)
        self.assertEqual(self.ui._fixed_cadence.deadline_ns, self.now[0] + 100000000)


class SimpleFixedCadenceUITests(unittest.TestCase):
    close_ui = simple.LiveAutoUITests.close_ui

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        simple.LiveAutoUITests.setUp(self)
        self.now = [1000000000]
        self.ui._pacing_clock_ns = lambda: self.now[0]

    def test_simple_analysis_120ms_leaves_80ms_and_publishes_start_before_refresh(self):
        self.ui.simple_auto_checkbox.setChecked(True)
        self.ui.allow_guess_checkbox.setChecked(True)
        self.now[0] += 200000000
        entered = self.now[0]
        original = simple.analyze_position
        def analyze(*args):
            self.now[0] += 120000000
            return original(*args)
        with patch('core_engine.random.sample', return_value=[(1, 1)]), \
                patch('ui_manager.analyze_position', side_effect=analyze):
            self.ui._simple_auto_timeout_slot()
        self.assertEqual(self.ui._fixed_cadence.started_ns, entered)
        self.assertEqual(self.ui._simple_auto_timer.interval(), 80)
        self.ui._simple_auto_timeout_slot()
        self.assertEqual(self.ui.live_auto_totals['auto_inputs'], 1)

    def test_open_flag_chord_each_commit_one_input_anchor(self):
        self.engine.reset_with_mines(3, 3, 1, {(1, 1)})
        for action, target in ((Action.OPEN, (0, 0)), (Action.FLAG, (1, 1)), (Action.CHORD, (0, 0))):
            with self.subTest(action=action):
                before = self.engine.get_counter_snapshot()
                self.now[0] += 200000000
                published = []
                refresh = self.ui._refresh_live_board
                def capture(*args, **kwargs):
                    published.append(self.ui._fixed_cadence.started_ns)
                    return refresh(*args, **kwargs)
                with patch.object(self.ui, '_refresh_live_board', side_effect=capture):
                    self.ui._apply_live_action(*target, action, auto_observation=self.engine.get_observation())
                after = self.engine.get_counter_snapshot()
                self.assertEqual(after['active_clicks'] + after['wasted_clicks'],
                                 before['active_clicks'] + before['wasted_clicks'] + 1)
                self.assertEqual(published, [self.now[0]])

    def test_step_exception_never_commits_or_rearms_a_cadence(self):
        self.ui.simple_auto_checkbox.setChecked(True)
        self.now[0] += 200000000
        with patch.object(self.engine, 'step', side_effect=RuntimeError('step failure')):
            self.ui._simple_auto_timeout_slot()
        self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
        self.assertIsNone(self.ui._fixed_cadence)
        self.assertEqual(self.engine.get_counter_snapshot()['active_clicks'], 0)
