"""Actual offscreen Main/engine/recorder with a controllable K actor seam."""
from dataclasses import replace
import os
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

import live_k_policy as k
from core_engine import Action, GameStatus, MinesweeperEngine
from live_policy import POLICY_K, POLICY_V1, POLICY_SIMPLE
from stage3_physical import load_timing_table
from tests.test_live_auto import SyntheticLivePolicyJob
from tests.ui_settings import isolate_ui_settings
from ui_manager import MinesweeperUI


class KUIFakeJob(SyntheticLivePolicyJob):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.owner = None
        self.validation = self.accepted_nonce = self.permit = None
        self.validations = []

    def start(self, snapshot):
        run = super().start(snapshot)
        if type(snapshot) is k.KSnapshot:
            self.owner = k.KOwner(snapshot, load_timing_table())
        return run

    def compute(self):
        self.deliver(self.owner.propose(self.requests[-1]))

    def validate_pending(self, snapshot, nonce):
        assert self.state == 'pending'
        self.validation = k.KValidation(snapshot, self.pending.token, nonce, self.pending.pending_m_revision)
        self.validations.append(self.validation)
        self.accepted_nonce = nonce
        self.state = 'validating'

    def invalidate_admission(self):
        self.accepted_nonce = None
        if self.state == 'admitted':
            self.permit = None
            self.state = 'pending'

    def deliver_admission(self):
        permit = self.owner.validate(self.validation)
        self.permit = permit
        self.state = 'admitted' if self.accepted_nonce == permit.nonce else 'pending'
        self.admitted.emit(permit)
        return permit

    def mark_applying(self, token, nonce=None):
        assert self.state == 'admitted' and token == self.pending.token
        assert nonce == self.accepted_nonce == self.permit.nonce
        self.state = 'applying'
        self.applied.append(token)
        return self.pending

    def acknowledge(self, status, observation=None):
        if self.ack_error:
            raise self.ack_error
        self.acks.append(k.make_ack(self.permit, status, observation))
        self.state = 'acknowledging'

    def deliver_ack(self):
        ack = self.acks[-1]
        self.owner.acknowledge(ack)
        self.pending = None
        self.state = 'ready'
        self.acknowledged.emit(ack)

    def shutdown(self):
        if self.active_run_id is not None and self.owner is not None:
            self.last_record = {'run_id': self.active_run_id, 'policy_id': POLICY_K,
                                'status': 'CLOSED', 'intent_reason': 'close', 'error': None,
                                'reaped': True, 'tree_active_count': 0, 'cleanup_complete': True}
            self.records.append(self.last_record)
        super().shutdown()


class LiveKUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        isolate_ui_settings(self)
        for target, value in (('ui_manager.LivePolicyJob', KUIFakeJob),
                              ('ui_manager.MinesweeperUI._ensure_zini_metric_job', None),
                              ('ui_manager.QMessageBox.information', None),
                              ('ui_manager.QMessageBox.warning', None),
                              ('ui_manager.QFileDialog.getOpenFileName', ('', '')),
                              ('ui_manager.QFileDialog.getSaveFileName', ('', '')),
                              ('ui_manager.QFileDialog.getExistingDirectory', '')):
            p = patch(target, value) if target.endswith('LivePolicyJob') else patch(target, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        self.engine = MinesweeperEngine(9, 9, 10)
        self.ui = MinesweeperUI(self.engine)
        self.addCleanup(self.close_ui)
        self.ui.live_policy_combo.setCurrentIndex(self.ui.live_policy_combo.findData(POLICY_K))
        self.ui.on_reset()
        self.job = self.ui._v1_job
        # Layout is only provided to engine placement, never to the owner/DTO.
        mines = [(1, 0), (3, 2), (4, 4), (8, 8), (2, 7), (6, 2), (8, 3), (7, 5), (4, 8), (0, 6)]
        placement = patch('core_engine.random.sample', return_value=mines)
        placement.start()
        self.addCleanup(placement.stop)

    def close_ui(self):
        self.ui._stop_timer()
        self.ui.close()
        self.ui.deleteLater()
        self.app.processEvents()

    def start(self):
        self.ui.simple_auto_checkbox.setChecked(True)
        self.job.compute()
        return self.job.pending

    def tick(self):
        self.ui._simple_auto_timer.timeout.emit()

    def apply_initial(self):
        p = self.start()
        self.tick()
        a = self.job.deliver_admission()
        return p, a

    def test_selection_analysis_only_and_supported_presets_do_not_input(self):
        self.assertEqual(self.job.requests, [])
        self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
        self.assertFalse(self.ui.allow_guess_checkbox.isChecked())
        self.ui.on_analyze_current()
        self.job.compute()
        for _ in range(3):
            self.ui.on_analyze_current()
            self.ui.simple_auto_interval_spin.setValue(500)
        self.assertEqual(len(self.job.requests), 1)
        self.assertEqual(self.job.validations, [])
        self.assertEqual(self.ui._live_action_count, 0)
        self.assertEqual(self.ui._replay_recorder.source_type, 'human')
        self.assertEqual(set(self.ui._analysis_result.overlays), {(0, 0)})
        self.assertTrue(self.ui.live_policy_combo.model().item(3).isEnabled())
        self.assertTrue(self.ui.live_policy_combo.model().item(4).isEnabled())

    def test_display_toggles_never_start_native_owner(self):
        self.ui.analysis_checkbox.setChecked(True)
        self.ui.probability_checkbox.setChecked(True)
        self.ui.analysis_checkbox.setChecked(False)
        self.ui.analysis_checkbox.setChecked(True)
        self.assertEqual(self.job.requests, [])
        self.assertEqual(self.ui._live_action_count, 0)
        self.ui.simple_auto_checkbox.setChecked(True)
        self.assertEqual(len(self.job.requests), 1)

    def test_app_initial_hidden_requires_explicit_reset_before_first_k_owner(self):
        other = MinesweeperUI(MinesweeperEngine(9, 9, 10))
        try:
            other.live_policy_combo.setCurrentIndex(other.live_policy_combo.findData(POLICY_K))
            other.simple_auto_checkbox.setChecked(True)
            self.assertFalse(other._k_reset_ready)
            self.assertEqual(other._v1_job.requests, [])
            other.on_reset()
            other.simple_auto_checkbox.setChecked(True)
            self.assertEqual(len(other._v1_job.requests), 1)
        finally:
            other.close()
            other.deleteLater()
            self.app.processEvents()

    def test_all_presets_accepted_and_custom_rejected_without_input(self):
        for size in ((9, 9, 10), (16, 16, 40), (30, 16, 99)):
            with self.subTest(size=size), patch.object(self.ui, 'engine', MinesweeperEngine(*size)):
                self.assertTrue(self.ui._v1_supported())
        with patch.object(self.ui, 'engine', MinesweeperEngine(3, 3, 1)):
            self.ui.on_analyze_current()
            self.assertFalse(self.ui._v1_supported())
        self.assertEqual(self.job.requests, [])
        self.assertEqual(self.ui._live_action_count, 0)

    def test_pause_during_validate_late_admission_zero_input_then_new_nonce_once(self):
        p = self.start()
        self.tick()
        old_nonce = self.ui._k_validation_nonce
        self.ui.simple_auto_checkbox.setChecked(False)
        stale = self.job.deliver_admission()
        self.assertEqual(self.ui._live_action_count, 0)
        self.assertIs(self.ui._v1_pending, p)
        self.ui.simple_auto_checkbox.setChecked(True)
        self.tick()
        self.assertNotEqual(self.ui._k_validation_nonce, old_nonce)
        current_nonce = self.ui._k_validation_nonce
        self.job.admitted.emit(stale)
        self.assertEqual(self.ui._k_validation_nonce, current_nonce)
        accepted = self.job.deliver_admission()
        self.job.admitted.emit(accepted)
        self.assertEqual(self.ui._live_action_count, 1)
        self.assertEqual(len(self.ui._replay_recorder.events), 1)
        self.assertEqual(len(self.job.applied), 1)

    def test_interval_change_during_validate_revokes_and_reuses_original_graph(self):
        p = self.start()
        self.tick()
        self.ui.simple_auto_interval_spin.setValue(500)
        self.job.deliver_admission()
        self.assertEqual(self.ui._live_action_count, 0)
        self.assertIs(self.ui._v1_pending, p)
        self.tick()
        self.job.deliver_admission()
        self.assertEqual(self.ui._live_action_count, 1)
        self.assertEqual(len(self.job.requests), 1)

    def test_actual_event_cost_ack_barrier_and_human_provenance(self):
        p, admitted = self.apply_initial()
        self.assertEqual(self.engine.status, GameStatus.PLAYING)
        self.assertEqual(len(self.job.requests), 1)
        self.assertEqual(self.ui._replay_recorder.source_type, 'algorithm')
        self.assertEqual(self.ui.live_auto_totals['k_inputs'], 1)
        self.assertEqual(self.ui.live_auto_totals['k_modeled_us'], p.modeled_action_us)
        self.assertEqual(self.ui.live_action_records[-1]['ack_state'], 'SENT')
        self.ui.simple_auto_checkbox.setChecked(False)
        self.job.deliver_ack()
        self.assertEqual(self.ui.live_action_records[-1]['ack_state'], 'ACKED')
        self.assertEqual(len(self.job.requests), 1)
        self.ui.on_left_click(2, 0)
        self.assertEqual(self.ui._replay_recorder.source_type, 'algorithm')
        self.assertFalse(self.ui._k_retired)
        self.job.complete_cancel()
        self.ui.on_reset()
        self.assertEqual(self.ui._replay_recorder.source_type, 'human')
        self.assertEqual(self.ui.live_auto_totals['k_inputs'], 0)

    def test_guess_wait_preserves_pending_and_late_guess_off_admission_is_zero(self):
        self.apply_initial()
        self.job.deliver_ack()
        self.job.compute()
        p = self.job.pending
        self.assertTrue(p.is_guess)
        self.assertFalse(self.ui._simple_auto_pending)
        self.ui.on_analyze_current()
        self.assertEqual(len(self.job.requests), 2)
        self.ui.allow_guess_checkbox.setChecked(True)
        self.tick()
        self.ui.allow_guess_checkbox.setChecked(False)
        self.job.deliver_admission()
        self.assertEqual(self.ui._live_action_count, 1)
        self.assertIs(self.ui._v1_pending, p)
        self.assertEqual(len(self.job.requests), 2)

    def test_manual_first_press_invalidates_before_original_right_gesture(self):
        self.start()
        self.tick()
        self.ui.show()
        button = self.ui._buttons[(2, 2)]
        QTest.mousePress(button, Qt.RightButton)
        self.assertFalse(self.ui._v1_owned)
        self.assertFalse(self.ui._k_retired)
        self.assertEqual(self.ui._replay_recorder.events[-1].action, 'FLAG')
        self.assertEqual(self.ui._live_action_count, 1)
        self.job.deliver_admission()
        self.assertEqual(self.ui._live_action_count, 1)
        QTest.mouseRelease(button, Qt.RightButton)
        self.assertEqual(self.ui._live_action_count, 1)

    def test_same_grid_different_revision_rejects_admission(self):
        self.start()
        self.tick()
        self.ui._live_action_count += 1
        self.job.deliver_admission()
        self.assertEqual(len(self.ui._replay_recorder.events), 0)
        self.assertTrue(self.ui._k_retired)

    def test_normal_retire_allows_new_owner_after_cleanup(self):
        self.start()
        self.ui._retire_v1_for_manual("manual handoff")
        self.job.complete_cancel()
        self.ui.on_analyze_current()
        self.assertEqual(len(self.job.requests), 2)
        self.assertNotEqual(self.job.requests[0].run_id, self.job.requests[1].run_id)
        self.ui.live_policy_combo.setCurrentIndex(self.ui.live_policy_combo.findData(POLICY_V1))
        self.job.complete_cancel()
        self.ui.on_analyze_current()
        self.assertEqual(len(self.job.requests), 3)

    def test_rehidden_board_adoption_never_resets_or_unflags(self):
        self.ui.on_right_click(2, 2)
        self.ui.on_right_click(2, 2)
        before = self.engine.get_observation()
        self.ui.on_analyze_current()
        self.assertEqual(len(self.job.requests), 1)
        self.assertEqual(self.job.requests[0].entry_mode, k.ADOPT_CURRENT)
        self.assertEqual(self.engine.get_observation(), before)
        self.assertEqual(self.ui._live_action_count, 2)

    def test_cleanup_failure_blocks_simple_v1_and_k_new_owners_even_after_reset(self):
        self.start()
        self.ui._retire_v1_for_manual("manual handoff")
        self.job.complete_cancel(cleanup=False)
        for policy in (POLICY_SIMPLE, POLICY_V1, POLICY_K):
            with self.subTest(policy=policy):
                self.ui.live_policy_combo.setCurrentIndex(self.ui.live_policy_combo.findData(policy))
                self.ui.on_reset()
                self.ui.on_analyze_current()
                self.assertEqual(len(self.job.requests), 1)
                self.assertFalse(self.ui.simple_auto_checkbox.isEnabled())

    def test_ack_send_failure_preserves_actual_event_cost_and_incomplete_record(self):
        self.start()
        self.tick()
        self.job.ack_error = OSError('ACK publication fixture')
        self.job.deliver_admission()
        self.assertEqual(len(self.ui._replay_recorder.events), 1)
        record = self.ui.live_action_records[-1]
        self.assertEqual(record['event_index'], 0)
        self.assertIn('ACK publication', record['incomplete_reason'])
        self.assertFalse(record['ack_sent'])
        self.assertEqual(self.ui.live_auto_totals['k_inputs'], 1)
        self.assertTrue(self.ui._live_input_uncertain)

    def test_failure_after_event_append_preserves_one_actual_event_and_owner_archive(self):
        self.start()
        self.tick()
        with patch.object(self.ui, '_refresh_live_board', side_effect=RuntimeError('post-step render fixture')):
            self.job.deliver_admission()
        record = self.ui.live_action_records[-1]
        self.assertEqual(record['event_index'], 0)
        self.assertIn('post-step render', record['incomplete_reason'])
        self.assertEqual(self.ui.live_auto_totals['k_inputs'], 1)
        self.assertEqual(self.job.acks, [])
        self.job.complete_cancel()
        self.ui.on_reset()
        self.assertEqual(self.ui.live_action_records, [])
        old = self.ui.live_owner_records[-1]['k_actions'][-1]
        self.assertIs(old, record)
        self.assertTrue(old['cleanup']['cleanup_complete'])

    def test_terminal_initial_input_has_one_event_cost_and_no_terminal_observation_in_ack(self):
        # Ten mines form the last row plus one corner, so first zero flood wins.
        with patch('core_engine.random.sample', return_value=[(x, 8) for x in range(9)] + [(8, 7)]):
            p, _ = self.apply_initial()
        self.assertEqual(self.engine.status, GameStatus.WON)
        self.assertEqual(len(self.ui._replay_recorder.events), 1)
        self.assertEqual(self.ui.live_auto_totals['k_inputs'], 1)
        self.assertEqual(self.ui.live_auto_totals['modeled_us'], p.modeled_action_us)
        self.assertIsNone(self.job.acks[-1].observation)
        self.assertEqual(len(self.job.requests), 1)

    def test_close_intent_rejects_validation_reply(self):
        self.start()
        self.tick()
        self.ui.close()
        self.job.deliver_admission()
        self.assertEqual(self.ui._live_action_count, 0)

    def test_close_before_ack_response_binds_cleanup_and_incomplete_cause(self):
        self.apply_initial()
        record = self.ui.live_action_records[-1]
        self.ui.close()
        self.assertEqual(record['ack_state'], 'INCOMPLETE')
        self.assertEqual(record['incomplete_reason'], 'close')
        self.assertTrue(record['cleanup']['cleanup_complete'])
        self.assertEqual(self.ui.live_owner_records[-1]['cleanup']['status'], 'CLOSED')

    def test_close_cleanup_failure_keeps_owner_receipt_and_blocks_restart(self):
        self.apply_initial()
        record = self.ui.live_action_records[-1]
        self.job.last_record = {'run_id': self.ui._live_run_id, 'policy_id': POLICY_K,
                               'status': 'FAILED', 'error': 'SHUTDOWN_CLEANUP: fixture',
                               'reaped': True, 'tree_active_count': 0, 'cleanup_complete': False}
        self.job.state = 'blocked'
        with patch.object(self.job, 'shutdown', side_effect=RuntimeError('cleanup fixture')):
            self.assertFalse(self.ui.close())
        self.assertFalse(record['cleanup']['cleanup_complete'])
        self.assertEqual(record['incomplete_reason'], 'SHUTDOWN_CLEANUP: fixture')
        self.assertFalse(self.ui.simple_auto_checkbox.isEnabled())


if __name__ == '__main__':
    unittest.main()
