"""Actual offscreen Main: new FLAG-free segments with explicit fake jobs only."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

import live_k_policy as k
import live_policy as v1
from core_engine import Action, GameStatus, MinesweeperEngine
from replay_player import ReplayPlayer
from stage3_physical import action_cost, load_timing_table
from tests import test_live_k_ui as fixtures
from tests.test_live_auto import SyntheticLivePolicyJob
from ui_manager import ChordMode, MinesweeperUI


class AdoptUIJob(fixtures.KUIFakeJob):
    """Same K seam, also permits a real frozen V1 proposal before switching."""
    def mark_applying(self, token, nonce=None):
        if isinstance(self.pending, k.KProposal):
            return super().mark_applying(token, nonce)
        return SyntheticLivePolicyJob.mark_applying(self, token)

    def acknowledge(self, status, observation=None):
        if isinstance(self.pending, k.KProposal):
            return super().acknowledge(status, observation)
        return SyntheticLivePolicyJob.acknowledge(self, status, observation)

    def deliver_ack(self):
        if isinstance(self.acks[-1], k.KAck):
            return super().deliver_ack()
        return SyntheticLivePolicyJob.deliver_ack(self)


class KAdoptUITests(unittest.TestCase):
    close_ui = fixtures.LiveKUITests.close_ui
    tick = fixtures.LiveKUITests.tick
    start = fixtures.LiveKUITests.start
    apply_initial = fixtures.LiveKUITests.apply_initial

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        with patch.object(fixtures, 'KUIFakeJob', AdoptUIJob):
            fixtures.LiveKUITests.setUp(self)
        self.ui.simple_auto_interval_spin.setValue(2000)

    def select(self, policy):
        self.ui.live_policy_combo.setCurrentIndex(self.ui.live_policy_combo.findData(policy))

    def assert_adopt_start(self, revision, cursor):
        state = self.job.requests[-1]
        self.assertIs(type(state), k.KSnapshot)
        self.assertEqual(state.entry_mode, k.ADOPT_CURRENT)
        self.assertEqual(state.definition, k.ADOPT_DEFINITION)
        self.assertEqual((state.input_seq, state.start_input_revision, state.input_revision), (0, revision, revision))
        self.assertEqual((state.base_m_revision, state.base_m), (0, ()))
        self.assertEqual(state.cursor, cursor)
        return state

    def arm_adopt(self):
        self.ui.on_left_click(0, 0)
        self.ui.simple_auto_checkbox.setChecked(True)
        self.job.compute()
        if self.job.pending.is_guess:
            self.ui.allow_guess_checkbox.setChecked(True)
        self.tick()
        self.assertEqual(self.job.state, 'validating')
        return self.job.pending

    def test_manual_current_board_is_adopted_without_reset_or_replay_loss(self):
        self.ui.on_left_click(0, 0)
        before = self.engine.get_observation()
        game = self.ui._live_game_id
        events = tuple(self.ui._replay_recorder.events)
        self.ui.on_analyze_current()
        self.assert_adopt_start(1, (0, 0))
        self.job.compute()
        self.assertFalse(self.job.pending.initial)
        self.assertEqual(self.engine.get_observation(), before)
        self.assertEqual(self.ui._live_game_id, game)
        self.assertEqual(self.ui.live_owner_records[-1]['phase'], 'K_P0')
        self.assertEqual(tuple(self.ui._replay_recorder.events), events)
        self.assertEqual(self.ui._replay_recorder.source_type, 'human')
        self.assertEqual(self.job.validations, [])

    def test_manual_start_in_original_app_game_does_not_require_an_extra_reset(self):
        other = MinesweeperUI(MinesweeperEngine(9, 9, 10))
        try:
            other.on_left_click(0, 0)
            other.live_policy_combo.setCurrentIndex(other.live_policy_combo.findData(v1.POLICY_K))
            other.on_analyze_current()
            self.assertFalse(other._k_reset_ready)
            self.assertEqual(len(other._v1_job.requests), 1)
            self.assertEqual(other._v1_job.requests[0].entry_mode, k.ADOPT_CURRENT)
        finally:
            other.close()
            other.deleteLater()
            self.app.processEvents()

    def test_simple_actual_input_then_k_has_a_new_segment_and_keeps_cost_separate(self):
        self.select(v1.POLICY_SIMPLE)
        self.ui.simple_auto_checkbox.setChecked(True)
        self.tick()
        self.assertEqual(self.ui._live_action_count, 1)
        self.assertEqual(self.ui.live_auto_totals['simple_inputs'], 1)
        self.select(v1.POLICY_K)
        self.assertEqual(self.job.requests, [])
        self.ui.on_analyze_current()
        self.assert_adopt_start(1, (0, 0))
        self.assertEqual(self.ui.live_auto_totals['k_modeled_us'], 0)
        self.assertEqual(self.ui._replay_recorder.source_type, 'algorithm')

    def test_v1_actual_input_then_k_waits_for_cleanup_and_preserves_global_revision(self):
        self.select(v1.POLICY_V1)
        self.ui.simple_auto_checkbox.setChecked(True)
        self.job.deliver(v1.plan_snapshot(self.job.requests[-1]))
        self.tick()
        self.ui.simple_auto_checkbox.setChecked(False)
        self.job.deliver_ack()
        self.assertEqual(self.ui._live_action_count, 1)
        old_run = self.job.active_run_id
        self.select(v1.POLICY_K)
        self.ui.on_analyze_current()
        self.assertEqual(len(self.job.requests), 1)
        self.job.complete_cancel()
        self.ui.on_analyze_current()
        state = self.assert_adopt_start(1, (0, 0))
        self.assertNotEqual(state.run_id, old_run)
        self.assertEqual(self.ui.live_auto_totals['v1_inputs'], 1)
        self.assertEqual(self.ui.live_auto_totals['k_inputs'], 0)

    def test_existing_flags_start_bootstrap_without_input_then_manual_readopt(self):
        self.ui.on_right_click(2, 2)
        before = self.engine.get_observation()
        with patch.object(self.engine, 'step', wraps=self.engine.step) as step:
            self.ui.on_analyze_current()
            self.ui.simple_auto_checkbox.setChecked(True)
            step.assert_not_called()
        self.assertEqual(len(self.job.requests), 1)
        self.assertEqual(self.job.requests[0].entry_mode, k.FLAG_ADOPT)
        self.assertEqual(self.engine.get_observation(), before)
        self.ui.on_right_click(2, 2)
        self.job.complete_cancel()
        self.ui.on_analyze_current()
        self.assert_adopt_start(2, (2, 2))

    def test_all_hidden_after_flag_unflag_uses_normal_guess_off_gate(self):
        self.ui.on_right_click(8, 8)
        self.ui.on_right_click(8, 8)
        self.assertTrue(self.engine.get_board_snapshot().mines_placed)
        self.ui.simple_auto_checkbox.setChecked(True)
        self.job.compute()
        self.assert_adopt_start(2, (8, 8))
        self.assertTrue(self.job.pending.is_guess)
        self.assertFalse(self.job.pending.initial)
        self.tick()
        self.assertEqual(self.job.validations, [])
        self.assertEqual(len(self.ui._replay_recorder.events), 2)
        self.assertEqual(self.ui._replay_recorder.source_type, 'human')

    def test_more_than_480_known_manual_inputs_still_start_local_sequence_zero(self):
        with patch.object(self.ui, '_refresh_live_board'):
            for _ in range(502):
                self.ui.on_right_click(8, 8)
        self.ui.on_analyze_current()
        state = self.assert_adopt_start(502, (8, 8))
        self.assertEqual(len(self.ui._replay_recorder.events), 502)
        self.assertEqual(state.start_input_revision, 502)
        self.assertEqual(self.ui.live_auto_totals['k_inputs'], 0)

    def test_untracked_external_input_with_same_grid_is_not_known_history(self):
        self.ui.on_left_click(0, 0)
        before = self.engine.get_observation()
        self.engine.step(0, 0, Action.OPEN)
        self.assertEqual(self.engine.get_observation(), before)
        self.ui.on_analyze_current()
        self.assertEqual(self.job.requests, [])
        self.assertIn('입력 이력', self.ui.live_policy_status_label.text())

    def test_unknown_preplaced_app_state_is_not_reconstructed_from_a_new_input(self):
        engine = MinesweeperEngine(9, 9, 10)
        engine.step(0, 0, Action.OPEN)
        other = MinesweeperUI(engine)
        try:
            other.on_right_click(8, 0)
            other.on_right_click(8, 0)
            other.live_policy_combo.setCurrentIndex(other.live_policy_combo.findData(v1.POLICY_K))
            other.on_analyze_current()
            self.assertEqual(other._v1_job.requests, [])
            self.assertFalse(other._known_live_history())
        finally:
            other.close()
            other.deleteLater()
            self.app.processEvents()

    def test_normal_retire_discards_pending_m_graph_and_readopts_new_empty_session(self):
        mines = ([(x, y) for y in range(3, 6) for x in range(3, 6) if (x, y) != (4, 4)]
                 + [(7, 7), (7, 8)])
        with patch('core_engine.random.sample', return_value=mines):
            self.apply_initial()
        self.job.deliver_ack()
        self.job.compute()
        old_owner = self.job.owner
        old = self.job.pending
        self.assertTrue(old.preinput_m)
        game = self.ui._live_game_id
        self.ui._retire_v1_for_manual("manual handoff")
        self.assertFalse(self.ui._k_retired)
        self.assertIsNone(self.ui._analysis_result)
        self.assertEqual(self.ui._k_base_m, ())
        self.ui.on_analyze_current()
        self.assertEqual(len(self.job.requests), 2)
        self.job.complete_cancel()
        self.ui.on_analyze_current()
        state = self.assert_adopt_start(1, (0, 0))
        self.assertNotEqual(state.run_id, old.snapshot.run_id)
        self.assertIsNot(self.job.owner, old_owner)
        self.assertEqual(self.job.owner.session.M, frozenset())
        self.assertIsNone(self.job.owner.selection)
        self.assertEqual(self.ui._live_game_id, game)
        self.assertEqual(self.ui.live_owner_records[-2]['end_revision'], 1)
        self.assertEqual(self.ui.live_owner_records[-1]['start_event_index'], 1)

    def test_policy_roundtrip_changes_no_board_then_new_k_owner(self):
        self.ui.on_left_click(0, 0)
        self.ui.on_analyze_current()
        old = self.job.requests[-1]
        before = self.engine.get_observation()
        self.select(v1.POLICY_SIMPLE)
        self.select(v1.POLICY_K)
        self.assertEqual(len(self.job.requests), 1)
        self.assertEqual(self.engine.get_observation(), before)
        self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
        self.job.complete_cancel()
        self.ui.on_analyze_current()
        self.assertNotEqual(self.assert_adopt_start(1, (0, 0)).run_id, old.run_id)

    def test_adopt_actual_input_one_event_one_cost_and_ack_then_no_extra_next(self):
        p = self.arm_adopt()
        a = self.job.deliver_admission()
        self.job.admitted.emit(a)
        self.assertEqual(self.ui._live_action_count, 2)
        self.assertEqual(len(self.ui._replay_recorder.events), 2)
        self.assertEqual(self.ui.live_auto_totals['k_inputs'], 1)
        self.assertEqual(self.ui.live_auto_totals['k_modeled_us'], p.modeled_action_us)
        self.assertEqual(self.ui._replay_recorder.source_type, 'algorithm')
        record = self.ui.live_action_records[-1]
        self.assertEqual((record['entry_mode'], record['definition']), (k.ADOPT_CURRENT, k.ADOPT_DEFINITION))
        self.assertEqual((record['start_input_revision'], record['input_seq'], record['event_index']), (1, 0, 1))
        self.assertEqual(record['M_before'], ())
        self.assertEqual(len(self.job.requests), 1)
        self.ui.simple_auto_checkbox.setChecked(False)
        self.job.deliver_ack()
        self.assertEqual(record['ack_state'], 'ACKED')
        self.assertEqual((self.ui._v1_input_seq, self.ui._k_m_revision), (1, 1))
        self.assertEqual(len(self.job.requests), 1)

    def test_first_model_c_leg_uses_last_actual_manual_cursor(self):
        self.ui.on_left_click(0, 0)
        self.ui.on_right_click(8, 0)
        self.ui.on_right_click(8, 0)
        self.ui.on_analyze_current()
        self.job.compute()
        p = self.job.pending
        self.assert_adopt_start(3, (8, 0))
        self.assertEqual(p.modeled_action_us, action_cost(load_timing_table(), (8, 0), (p.x, p.y)))
        self.assertEqual(self.ui.live_auto_totals['modeled_us'], 0)

    def test_retirement_during_unconfirmed_ack_is_failure_latched_across_policy_switch(self):
        self.arm_adopt()
        self.job.deliver_admission()
        self.ui._retire_v1_for_manual("manual handoff")
        self.assertFalse(self.ui._live_input_uncertain)
        self.assertIsNotNone(self.ui._k_retiring)
        # Exiting without the original ACK is still a real failure.
        self.job.complete_cancel()
        self.assertTrue(self.ui._live_input_uncertain)
        self.assertTrue(self.ui._k_retired)
        count = len(self.job.requests)
        for policy in (v1.POLICY_SIMPLE, v1.POLICY_V1, v1.POLICY_K):
            with self.subTest(policy=policy):
                self.select(policy)
                self.ui.simple_auto_checkbox.setChecked(True)
                self.assertEqual(len(self.job.requests), count)
                self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
        self.assertEqual(self.ui.live_action_records[-1]['ack_state'], 'INCOMPLETE')
        self.ui.on_reset()
        self.assertFalse(self.ui._live_input_uncertain)
        self.assertFalse(self.ui._k_retired)

    def test_worker_failure_after_policy_switch_is_not_normal_retirement(self):
        self.ui.on_left_click(0, 0)
        self.ui.on_analyze_current()
        run = self.job.active_run_id
        self.select(v1.POLICY_SIMPLE)
        self.job.state = 'idle'
        self.job.active_run_id = None
        self.job.finished.emit({'run_id': run, 'policy_id': v1.POLICY_K, 'status': 'FAILED',
                                'error': 'SETUP_OPEN_SURVIVED', 'cleanup_complete': True})
        self.select(v1.POLICY_K)
        self.ui.on_analyze_current()
        self.assertEqual(len(self.job.requests), 1)
        self.assertTrue(self.ui._k_retired)
        self.assertTrue(self.ui._live_input_uncertain)

    def test_stale_start_revision_with_same_grid_is_rejected_at_final_admission(self):
        self.arm_adopt()
        self.ui._k_start_input_revision += 1
        self.job.deliver_admission()
        self.assertEqual(len(self.ui._replay_recorder.events), 1)
        self.assertTrue(self.ui._k_retired)

    def test_old_owner_permit_cannot_authorize_the_new_owner(self):
        self.arm_adopt()
        old_owner = self.job.owner
        old = old_owner.validate(self.job.validation)
        self.ui._retire_v1_for_manual("manual handoff")
        self.job.complete_cancel()
        self.ui.simple_auto_checkbox.setChecked(True)
        self.job.compute()
        self.ui.allow_guess_checkbox.setChecked(True)
        self.tick()
        nonce = self.ui._k_validation_nonce
        self.job.admitted.emit(old)
        self.assertEqual(self.ui._k_validation_nonce, nonce)
        self.assertEqual(len(self.ui._replay_recorder.events), 1)
        self.job.deliver_admission()
        self.assertEqual(len(self.ui._replay_recorder.events), 2)

    def test_pause_and_display_changes_revalidate_same_adopt_graph(self):
        p = self.arm_adopt()
        graph = self.job.owner.selection
        self.ui.simple_auto_checkbox.setChecked(False)
        self.job.deliver_admission()
        for value in (True, False, True):
            self.ui.probability_checkbox.setChecked(value)
            self.ui.auto_cursor_checkbox.setChecked(value)
        self.ui.on_analyze_current()
        self.ui.simple_auto_checkbox.setChecked(True)
        self.tick()
        self.assertIs(self.job.pending, p)
        self.assertIs(self.job.owner.selection, graph)
        self.assertEqual(len(self.job.requests), 1)
        self.job.deliver_admission()
        self.assertEqual(len(self.ui._replay_recorder.events), 2)

    def stopped_admission(self, action):
        self.arm_adopt()
        if action == 'reset':
            self.ui.on_reset()
        elif action == 'replay':
            self.ui._enter_replay_mode(ReplayPlayer(self.ui._replay_recorder.to_replay_data()))
        else:
            self.ui.close()
        count = self.ui._live_action_count
        self.job.deliver_admission()
        self.assertEqual(self.ui._live_action_count, count)
        self.assertIsNone(self.ui._v1_pending)

    def test_reset_during_adopt_validation_has_zero_late_input(self):
        self.stopped_admission('reset')

    def test_replay_during_adopt_validation_has_zero_late_input(self):
        self.stopped_admission('replay')

    def test_close_during_adopt_validation_has_zero_late_input(self):
        self.stopped_admission('close')

    def manual_gesture(self, kind):
        self.arm_adopt()
        self.ui.show()
        self.app.processEvents()
        self.ui.on_chord_mode_changed(ChordMode.BOTH_CLICK if kind == 'both' else ChordMode.LEFT_CLICK)
        target = self.ui._buttons[(0, 0) if kind == 'both' else (3, 0)]
        position = self.ui.mapFromGlobal(target.mapToGlobal(target.rect().center()))
        native = self.ui.windowHandle()
        observations = []
        original = self.engine.step
        def step(*args):
            observations.append((self.ui._v1_owned, self.ui._v1_pending,
                                 self.ui._k_validation_nonce, self.ui._simple_auto_pending))
            return original(*args)
        with patch.object(self.engine, 'step', side_effect=step):
            button = Qt.RightButton if kind == 'right' else Qt.LeftButton
            QTest.mousePress(native, button, pos=position)
            if kind == 'both':
                QTest.mousePress(native, Qt.RightButton, pos=position)
            self.job.deliver_admission()
            self.job.complete_cancel()
            self.ui.on_analyze_current()
            self.assertEqual(len(self.job.requests), 1)
            if kind == 'both':
                QTest.mouseRelease(native, Qt.RightButton, pos=position)
            QTest.mouseRelease(native, button, pos=position)
        self.assertEqual(observations, [(False, None, None, False)])
        self.assertEqual(self.ui._live_action_count, 2)
        self.assertEqual(len(self.ui._replay_recorder.events), 2)
        self.assertFalse(self.ui._k_retired)
        self.assertEqual(self.ui._mouse_buttons, Qt.NoButton)

    def test_left_gesture_retires_before_original_release_and_waits_for_button_up(self):
        self.manual_gesture('left')

    def test_right_gesture_retires_before_original_press_and_waits_for_button_up(self):
        self.manual_gesture('right')

    def test_both_gesture_retires_before_original_chord_and_waits_for_button_up(self):
        self.manual_gesture('both')

