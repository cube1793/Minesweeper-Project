"""Offscreen Main LC0 parity and actual selection/record projection, fake IPC."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from core_engine import GameStatus
from experiments.program_k_capability import KLocalSession
import live_k_policy as k
from live_policy import POLICY_SIMPLE, POLICY_V1, POLICY_K, POLICY_K_LC0, plan_snapshot
from live_analysis import OverlayKind
from replay_player import ReplayPlayer
from tests import test_live_k_ui as base
from tests import test_live_k_flag_adopt_ui as flags
from tests import test_live_native_feedback as feedback
from tests.test_live_auto import SyntheticLivePolicyJob


class FamilyFakeJob(flags.FlagUIJob):
    def start(self, snapshot):
        self.start_snapshot = snapshot
        return super().start(snapshot)

    def compute(self):
        if type(self.requests[-1]) is k.KSnapshot:
            return super().compute()
        self.deliver(plan_snapshot(self.requests[-1]))

    def mark_applying(self, token, nonce=None):
        if type(self.pending) is k.KProposal:
            return super().mark_applying(token, nonce)
        return SyntheticLivePolicyJob.mark_applying(self, token)

    def acknowledge(self, status, observation=None):
        if type(self.pending) is k.KProposal:
            return super().acknowledge(status, observation)
        return SyntheticLivePolicyJob.acknowledge(self, status, observation)

    def deliver_ack(self):
        if type(self.acks[-1]) is k.KAck:
            return super().deliver_ack()
        return SyntheticLivePolicyJob.deliver_ack(self)

    def shutdown(self):
        super().shutdown()
        if self.last_record is not None:
            self.last_record['policy_id'] = self.start_snapshot.policy_id


class LiveLC0UITests(unittest.TestCase):
    close_ui = base.LiveKUITests.close_ui
    tick = base.LiveKUITests.tick
    mixed = flags.KFlagAdoptUITests.mixed
    arm = flags.KFlagAdoptUITests.arm
    arm_mode = feedback.KNativeFeedbackTests.arm_mode

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        with patch.object(base, 'KUIFakeJob', FamilyFakeJob):
            base.LiveKUITests.setUp(self)
        self.select(POLICY_K_LC0)
        self.ui.on_reset()
        self.ui.simple_auto_interval_spin.setValue(2000)

    def select(self, policy):
        self.ui.live_policy_combo.setCurrentIndex(self.ui.live_policy_combo.findData(policy))

    def test_lc0_enabled_label_p0_kept_lc1_disabled_and_three_presets(self):
        combo = self.ui.live_policy_combo
        for policy in (POLICY_K, POLICY_K_LC0):
            self.assertTrue(combo.model().item(combo.findData(policy)).isEnabled())
            self.assertIn('(\uc2e4\ud5d8\uc801)', combo.itemText(combo.findData(policy)))
        self.assertFalse(combo.model().item(combo.findData('K_LC1')).isEnabled())
        for index in (0, 1, 2):
            self.ui.difficulty_combo.setCurrentIndex(index)
            self.assertTrue(self.ui._v1_supported())
            self.ui.on_analyze_current()
            state = self.job.requests[-1]
            self.assertEqual((state.policy_id,state.definition,state.phase),
                             (POLICY_K_LC0,k.LC0_DEFINITION,k.PHASE_LC0))
            self.assertEqual(state.game_id,self.ui._live_game_id)
            self.assertEqual(self.ui._live_action_count,0)
            self.ui._invalidate_v1_run('test preset')
            self.job.complete_cancel()
        with patch.object(self.ui.difficulty_combo,'currentText',return_value='\ucee4\uc2a4\ud140'):
            self.assertFalse(self.ui._v1_supported())

    def test_preparation_then_normal_same_session_policy_definition_and_replay(self):
        self.arm()
        session=self.job.owner.session
        for index in range(2):
            if index:
                self.job.compute(); self.tick()
            p=self.job.pending
            self.job.deliver_admission()
            self.job.deliver_ack()
            record=self.ui.live_action_records[-1]
            self.assertEqual(record['policy_id'],POLICY_K_LC0)
            self.assertEqual(record['definition'],k.LC0_FLAG_ADOPT_DEFINITION)
            self.assertEqual(record['semantic_input'],'UNFLAG')
            self.assertEqual(record['ack_state'],'ACKED')
            self.assertEqual(record['expected_ack']['permit']['proposal']['snapshot']['game_id'],self.ui._live_game_id)
        self.assertEqual(self.ui._k_phase,k.PHASE_LC0)
        self.assertEqual(self.ui.live_owner_records[-1]['k_start_revision'],10)
        self.job.compute()
        p=self.job.pending
        self.assertIs(self.job.owner.session,session)
        self.assertIs(self.job.owner.selection,self.job.owner.distance_selection.selected)
        self.assertEqual(p.snapshot.phase,k.PHASE_LC0)
        self.assertIn('K-LC0',self.ui._analysis_result.status_text)
        self.assertEqual(self.ui._analysis_result.move,p.move)
        self.tick(); self.job.deliver_admission()
        self.ui.simple_auto_checkbox.setChecked(False)
        self.job.deliver_ack()
        record=self.ui.live_action_records[-1]
        self.assertEqual((record['policy_id'],record['phase'],record['ack_state']),(POLICY_K_LC0,k.PHASE_LC0,'ACKED'))
        event=self.ui._replay_recorder.events[record['event_index']]
        self.assertEqual((event.action,event.x,event.y),(p.action,p.x,p.y))
        self.assertEqual(self.ui._replay_recorder.source_type,'algorithm')

    def test_all_entries_ack_manual_left_right_both(self):
        feedback.KNativeFeedbackTests.test_ack_window_all_entries_and_manual_gestures_preserves_current_state(self)

    def test_first_qtest_press_revokes_and_no_new_owner_while_held(self):
        feedback.KNativeFeedbackTests.test_first_press_revokes_before_release_and_no_new_owner_while_held(self)

    def test_repeated_manual_during_ack_keeps_sealed_input(self):
        feedback.KNativeFeedbackTests.test_multiple_manual_inputs_do_not_overwrite_sealed_ack(self)

    def test_duplicate_forged_ack_and_history_mutation_fail_closed(self):
        feedback.KNativeFeedbackTests.test_duplicate_or_forged_retiring_ack_is_fail_closed(self)
        feedback.KNativeFeedbackTests.test_history_mutation_during_retirement_is_rejected(self)

    def test_policy_definition_or_m_record_mutation_rejected_during_ack(self):
        for field,value in (('policy_id',POLICY_K),('definition',k.FLAG_ADOPT_DEFINITION),
                            ('start_input_revision',100),('pending_m_revision',50)):
            with self.subTest(field=field):
                case=type(self)(); case.setUp()
                try:
                    case.arm(); case.job.deliver_admission()
                    case.ui.on_right_click(5,0)
                    case.ui.live_action_records[-1][field]=value
                    case.job.deliver_ack()
                    self.assertTrue(case.ui._live_input_uncertain)
                finally: case.doCleanups()

    def test_pause_guess_interval_display_keep_original_choice_and_target(self):
        self.ui.on_left_click(0,0)
        self.ui.simple_auto_checkbox.setChecked(True)
        self.job.compute()
        p=self.job.pending
        choice=self.job.owner.distance_selection
        self.ui.simple_auto_checkbox.setChecked(False)
        count=len(self.job.requests)
        with patch.object(KLocalSession,'analyze_decision',side_effect=AssertionError('extra analyze')), \
                patch.object(self.job.owner,'_select',side_effect=AssertionError('extra select')):
            for enabled in (False,True):
                self.ui.probability_checkbox.setChecked(enabled)
                self.ui.auto_cursor_checkbox.setChecked(enabled)
                self.ui.analysis_checkbox.setChecked(enabled)
            self.ui.simple_auto_interval_spin.setValue(500)
            self.ui.on_analyze_current()
            self.ui.simple_auto_checkbox.setChecked(True)
            self.assertEqual(len(self.job.requests),count)
            if p.is_guess:
                self.tick()
                self.assertEqual(len(self.job.validations),0)
            self.ui.allow_guess_checkbox.setChecked(True)
            self.tick()
            self.ui.simple_auto_checkbox.setChecked(False)
            self.job.deliver_admission()
        self.assertIs(self.job.owner.distance_selection,choice)
        self.assertIs(self.ui._v1_pending,p)
        self.assertEqual(self.ui._analysis_result.move,p.move)
        self.assertEqual(self.ui._live_action_count,1)

    def test_both_directions_p0_lc0_and_v1_simple_policy_drain(self):
        for old,new in ((POLICY_K_LC0,POLICY_K),(POLICY_K,POLICY_K_LC0),
                        (POLICY_K_LC0,POLICY_V1),(POLICY_K_LC0,POLICY_SIMPLE)):
            with self.subTest(old=old,new=new):
                case=type(self)(); case.setUp()
                try:
                    case.select(old); case.arm(); case.job.deliver_admission()
                    ack=case.job.acks[-1]
                    requests=len(case.job.requests)
                    state=(case.engine.get_observation(),case.ui._live_action_count,case.ui._v1_cursor)
                    case.select(new)
                    case.ui.on_analyze_current()
                    self.assertEqual(len(case.job.requests),requests)
                    case.job.deliver_ack()
                    self.assertEqual(case.ui.live_action_records[-1]['policy_id'],old)
                    self.assertEqual(case.ui.live_action_records[-1]['ack_state'],'ACKED')
                    self.assertEqual((case.engine.get_observation(),case.ui._live_action_count,case.ui._v1_cursor),state)
                    self.assertEqual(len(case.job.requests),requests)
                    case.job.complete_cancel()
                    if k.is_k_policy(new):
                        case.ui.on_analyze_current()
                        self.assertEqual(case.job.requests[-1].policy_id,new)
                        self.assertNotEqual(case.job.requests[-1].run_id,ack.run_id)
                finally: case.doCleanups()

    def test_other_policy_valid_permit_rejected_with_zero_input(self):
        self.arm()
        p=self.job.pending
        a=self.job.owner.validate(self.job.validation)
        other=replace(p,snapshot=replace(p.snapshot,policy_id=POLICY_K,
                                        definition=k.FLAG_ADOPT_DEFINITION))
        self.job.state='admitted'
        before=self.ui._live_action_count
        self.job.admitted.emit(replace(a,proposal=other))
        self.assertEqual(self.ui._live_action_count,before)
        self.assertEqual(self.job.applied,[])
        self.assertTrue(self.ui._live_input_uncertain)

    def test_late_permit_reset_replay_policy_difficulty_close_has_no_input_or_residue(self):
        for mode in ('reset','replay','policy','difficulty','close'):
            with self.subTest(mode=mode):
                case=type(self)();case.setUp()
                try:
                    case.arm()
                    if mode=='reset': case.ui.on_reset()
                    elif mode=='replay': case.ui._enter_replay_mode(ReplayPlayer(case.ui._replay_recorder.to_replay_data()))
                    elif mode=='policy': case.select(POLICY_K)
                    elif mode=='difficulty': case.ui.difficulty_combo.setCurrentIndex(1)
                    else: case.ui.close()
                    before=case.ui._live_action_count
                    case.job.deliver_admission()
                    self.assertEqual(case.ui._live_action_count,before)
                    self.assertEqual(case.job.applied,[])
                    self.assertIsNone(case.ui._v1_pending)
                    self.assertFalse(case.ui.auto_cursor_overlay.isVisible())
                finally: case.doCleanups()

    def test_space_and_enter_after_lc0_selection_and_editor_focus(self):
        from PyQt5.QtWidgets import QLineEdit
        self.ui.show(); self.app.processEvents()
        self.ui.live_policy_combo.setFocus()
        for key in (Qt.Key_Space,Qt.Key_Return,Qt.Key_Enter):
            with self.subTest(key=key):
                before=self.ui._live_game_id
                QTest.keyClick(self.ui.live_policy_combo,key)
                self.app.processEvents()
                self.assertNotEqual(self.ui._live_game_id,before)
                self.assertEqual(self.ui._live_policy,POLICY_K_LC0)
        editor=QLineEdit(self.ui)
        editor.show(); editor.setFocus(); self.app.processEvents()
        before=self.ui._live_game_id
        QTest.keyClicks(editor,'abc ')
        QTest.keyClick(editor,Qt.Key_Return)
        self.assertEqual(editor.text(),'abc ')
        self.assertEqual(self.ui._live_game_id,before)
