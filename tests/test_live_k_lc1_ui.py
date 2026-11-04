"""LC1 Main parity using real native owners and explicit fake IPC delivery."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QLineEdit

import live_k_policy as k
from live_policy import POLICY_SIMPLE, POLICY_V1, POLICY_K, POLICY_K_LC0, POLICY_K_LC1
from tests import test_live_k_lc0_ui as lc0
from tests import test_live_k_ui as base
from tests import test_live_k_flag_adopt_ui as flags
from tests import test_live_native_feedback as feedback


class LiveLC1UITests(unittest.TestCase):
    close_ui = base.LiveKUITests.close_ui
    tick = base.LiveKUITests.tick
    mixed = flags.KFlagAdoptUITests.mixed
    arm = flags.KFlagAdoptUITests.arm
    arm_mode = feedback.KNativeFeedbackTests.arm_mode
    select = lc0.LiveLC0UITests.select

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        with patch.object(base, 'KUIFakeJob', lc0.FamilyFakeJob):
            base.LiveKUITests.setUp(self)
        self.select(POLICY_K_LC1)
        self.ui.on_reset()
        self.ui.simple_auto_interval_spin.setValue(2000)

    test_all_entries_ack_manual_left_right_both = lc0.LiveLC0UITests.test_all_entries_ack_manual_left_right_both
    test_first_qtest_press_revokes_and_no_new_owner_while_held = lc0.LiveLC0UITests.test_first_qtest_press_revokes_and_no_new_owner_while_held
    test_repeated_manual_during_ack_keeps_sealed_input = lc0.LiveLC0UITests.test_repeated_manual_during_ack_keeps_sealed_input
    test_duplicate_forged_ack_and_history_mutation_fail_closed = lc0.LiveLC0UITests.test_duplicate_forged_ack_and_history_mutation_fail_closed
    test_policy_definition_or_m_record_mutation_rejected_during_ack = lc0.LiveLC0UITests.test_policy_definition_or_m_record_mutation_rejected_during_ack
    test_pause_guess_interval_display_keep_original_choice_and_target = lc0.LiveLC0UITests.test_pause_guess_interval_display_keep_original_choice_and_target
    test_other_policy_valid_permit_rejected_with_zero_input = lc0.LiveLC0UITests.test_other_policy_valid_permit_rejected_with_zero_input
    test_late_permit_reset_replay_policy_difficulty_close_has_no_input_or_residue = lc0.LiveLC0UITests.test_late_permit_reset_replay_policy_difficulty_close_has_no_input_or_residue
    test_history_tampering_before_token_consumption = flags.KFlagAdoptUITests.test_history_only_tampering_blocks_preparation_before_token_consumption

    def test_enabled_experimental_label_all_three_presets_and_custom_block(self):
        combo = self.ui.live_policy_combo
        for policy in (POLICY_K, POLICY_K_LC0, POLICY_K_LC1):
            self.assertTrue(combo.model().item(combo.findData(policy)).isEnabled())
            self.assertIn('(실험적)', combo.itemText(combo.findData(policy)))
        for index in (0, 1, 2):
            with self.subTest(preset=index):
                self.ui.difficulty_combo.setCurrentIndex(index)
                self.assertTrue(self.ui._v1_supported())
                self.ui.on_analyze_current()
                state = self.job.requests[-1]
                self.assertEqual((state.policy_id, state.definition, state.phase),
                                 (POLICY_K_LC1, k.LC1_DEFINITION, k.PHASE_LC1))
                self.assertEqual(state.game_id, self.ui._live_game_id)
                self.assertEqual(self.ui._live_action_count, 0)
                self.ui._invalidate_v1_run('preset check')
                self.job.complete_cancel()
        with patch.object(self.ui.difficulty_combo, 'currentText', return_value='커스텀'):
            self.assertFalse(self.ui._v1_supported())

    def test_preparation_normal_same_session_record_replay_and_original_choice(self):
        self.arm()
        session = self.job.owner.session
        for index in range(2):
            if index:
                self.job.compute()
                self.tick()
            self.job.deliver_admission()
            self.job.deliver_ack()
            record = self.ui.live_action_records[-1]
            self.assertEqual(record['policy_id'], POLICY_K_LC1)
            self.assertEqual(record['definition'], k.LC1_FLAG_ADOPT_DEFINITION)
            self.assertEqual(record['semantic_input'], 'UNFLAG')
            self.assertEqual(record['ack_state'], 'ACKED')
            self.assertEqual(record['expected_ack']['permit']['proposal']['snapshot']['game_id'], self.ui._live_game_id)
        self.assertEqual(self.ui._k_phase, k.PHASE_LC1)
        self.assertEqual(self.ui.live_owner_records[-1]['k_start_revision'], 10)
        self.job.compute()
        p = self.job.pending
        original = self.job.owner.singleton_selection
        self.assertIs(self.job.owner.session, session)
        self.assertIs(self.job.owner.selection, original.selected)
        self.assertIs(self.job.owner.distance_selection, original.baseline)
        self.assertEqual(self.ui._analysis_result.move, original.selected.move)
        self.assertIn('K-LC1', self.ui._analysis_result.status_text)
        self.tick()
        self.job.deliver_admission()
        self.ui.simple_auto_checkbox.setChecked(False)
        self.job.deliver_ack()
        record = self.ui.live_action_records[-1]
        self.assertEqual((record['policy_id'], record['phase'], record['ack_state']),
                         (POLICY_K_LC1, k.PHASE_LC1, 'ACKED'))
        event = self.ui._replay_recorder.events[record['event_index']]
        self.assertEqual((event.action, event.x, event.y), (p.action, p.x, p.y))
        self.assertEqual(self.ui._replay_recorder.source_type, 'algorithm')
        self.assertIsNone(self.job.owner.singleton_selection)

    def test_three_preset_current_and_flag_entries_keep_actual_history(self):
        for index in (0, 1, 2):
            for flagged in (False, True):
                with self.subTest(preset=index, flagged=flagged):
                    self.ui.difficulty_combo.setCurrentIndex(index)
                    self.ui.on_reset()
                    with patch('core_engine.random.sample', side_effect=lambda population, count: list(population)[-count:]):
                        if flagged: self.ui.on_right_click(0, 0)
                        else: self.ui.on_both_click(0, 0)
                    self.ui.on_analyze_current()
                    state = self.job.requests[-1]
                    self.assertEqual(state.entry_mode, k.FLAG_ADOPT if flagged else k.ADOPT_CURRENT)
                    self.assertEqual(state.definition, k.LC1_FLAG_ADOPT_DEFINITION if flagged else k.LC1_ADOPT_DEFINITION)
                    self.assertEqual(state.start_input_revision, 1)
                    self.assertEqual(state.game_id, self.ui._live_game_id)
                    self.assertEqual(state.base_m, ())
                    self.assertTrue(self.ui._known_live_history())
                    self.ui._invalidate_v1_run('entry domain check')
                    self.job.complete_cancel()

    def test_p0_lc0_lc1_both_directions_and_simple_v1_after_ack(self):
        for old, new in ((POLICY_K_LC1, POLICY_K), (POLICY_K, POLICY_K_LC1),
                         (POLICY_K_LC1, POLICY_K_LC0), (POLICY_K_LC0, POLICY_K_LC1),
                         (POLICY_K_LC1, POLICY_V1), (POLICY_K_LC1, POLICY_SIMPLE)):
            with self.subTest(old=old, new=new):
                case = type(self)()
                case.setUp()
                try:
                    case.select(old)
                    case.arm()
                    case.job.deliver_admission()
                    ack = case.job.acks[-1]
                    requests = len(case.job.requests)
                    case.ui.on_right_click(5, 0)
                    state = (case.engine.get_observation(), case.ui._live_action_count, case.ui._v1_cursor)
                    case.select(new)
                    case.ui.on_analyze_current()
                    self.assertEqual(len(case.job.requests), requests)
                    case.job.deliver_ack()
                    self.assertEqual(case.ui.live_action_records[-1]['policy_id'], old)
                    self.assertEqual(case.ui.live_action_records[-1]['ack_state'], 'ACKED')
                    self.assertEqual((case.engine.get_observation(), case.ui._live_action_count, case.ui._v1_cursor), state)
                    self.assertEqual(case.ui._replay_recorder.source_type, 'algorithm')
                    case.job.complete_cancel()
                    if k.is_k_policy(new):
                        case.ui.simple_auto_checkbox.setChecked(True)
                        self.assertEqual(case.job.requests[-1].policy_id, new)
                        self.assertNotEqual(case.job.requests[-1].run_id, ack.run_id)
                        self.assertEqual(case.job.requests[-1].base_m, ())
                finally:
                    case.doCleanups()

    def test_space_enter_and_editor_focus(self):
        self.ui.show()
        self.app.processEvents()
        self.ui.live_policy_combo.setFocus()
        for key in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            with self.subTest(key=key):
                game = self.ui._live_game_id
                QTest.keyClick(self.ui.live_policy_combo, key)
                self.app.processEvents()
                self.assertNotEqual(self.ui._live_game_id, game)
                self.assertEqual(self.ui._live_policy, POLICY_K_LC1)
        editor = QLineEdit(self.ui)
        editor.show()
        editor.setFocus()
        self.app.processEvents()
        game = self.ui._live_game_id
        QTest.keyClicks(editor, 'abc ')
        QTest.keyClick(editor, Qt.Key_Return)
        self.assertEqual(editor.text(), 'abc ')
        self.assertEqual(self.ui._live_game_id, game)


if __name__ == '__main__':
    unittest.main()
