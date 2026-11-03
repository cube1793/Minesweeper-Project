"""Offscreen Main with retained native owners and an explicit fake job."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

import live_k_policy as k
from core_engine import Action, MinesweeperEngine
from experiments.program_k_capability import KLocalSession
from live_policy import POLICY_K, POLICY_SIMPLE, POLICY_V1
from replay_player import ReplayPlayer
from tests import test_live_k_ui as fixtures
from ui_manager import ChordMode, MinesweeperUI


UI_MINES = [(1, 0), (4, 0), (7, 0), (8, 0), (7, 1), (8, 1), (7, 2), (8, 2), (7, 3), (8, 3)]


class FlagUIJob(fixtures.KUIFakeJob):
    def compute(self):
        start = self.requests[-1]
        if start.phase == k.PHASE_BOOTSTRAP:
            self.state = 'ready'
            self.bootstrapped.emit((start, self.owner.expected))
        else:
            super().compute()


class KFlagAdoptUITests(unittest.TestCase):
    close_ui = fixtures.LiveKUITests.close_ui
    tick = fixtures.LiveKUITests.tick

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        with patch.object(fixtures, 'KUIFakeJob', FlagUIJob):
            fixtures.LiveKUITests.setUp(self)
        self.ui.simple_auto_interval_spin.setValue(2000)

    def mixed(self, auto=False):
        with patch('core_engine.random.sample', return_value=UI_MINES):
            for x, y in ((0, 0), (0, 1), (1, 1), (2, 0), (2, 1)):
                self.ui.on_left_click(x, y)
            for x in (1, 3, 4):
                self.ui.on_right_click(x, 0)
        if auto:
            self.ui.simple_auto_checkbox.setChecked(True)
        else:
            self.ui.on_analyze_current()
        self.job.compute()  # no-input bootstrap result
        self.job.compute()  # first preparation proposal
        self.assertEqual(self.job.pending.snapshot.bootstrap.retained, ((1, 0),))
        self.assertEqual((self.job.pending.x, self.job.pending.y), (3, 0))
        return self.job.pending

    def arm(self):
        p = self.mixed(auto=True)
        self.tick()
        self.assertEqual(self.job.state, 'validating')
        return p

    def test_analysis_only_preserves_game_flags_records_and_has_no_fake_probability(self):
        p = self.mixed()
        game = self.ui._live_game_id
        before = self.engine.get_observation()
        self.assertEqual(self.ui._live_action_count, 8)
        self.assertEqual(len(self.ui._replay_recorder.events), 8)
        self.assertEqual(self.ui.live_auto_totals['auto_inputs'], 0)
        self.assertEqual(self.ui._replay_recorder.source_type, 'human')
        self.assertIsNone(self.ui._analysis_result.decision)
        self.assertEqual(list(self.ui._analysis_result.overlays), [(3, 0)])
        self.assertIsNone(self.ui._analysis_result.overlays[(3, 0)].probability)
        self.assertIsNone(self.ui._analysis_result.overlays[(3, 0)].kind)
        for _ in range(3):
            self.tick()
            self.ui.on_analyze_current()
        self.assertIs(self.job.pending, p)
        self.assertEqual(self.engine.get_observation(), before)
        self.assertEqual(self.ui._live_game_id, game)
        self.assertEqual(len(self.job.requests), 2)
        self.assertEqual(self.job.validations, [])

    def test_real_preparation_event_cost_and_ack_are_separate_from_k(self):
        p = self.arm()
        permit = self.job.deliver_admission()
        self.job.admitted.emit(permit)
        self.assertEqual(self.ui._live_action_count, 9)
        self.assertEqual(len(self.ui._replay_recorder.events), 9)
        self.assertEqual(self.engine.get_observation()[0][1], -3)
        self.assertEqual(self.engine.get_observation()[0][3], -2)
        self.assertEqual(self.ui._replay_recorder.source_type, 'algorithm')
        self.assertEqual((self.ui.live_auto_totals['preparation_inputs'], self.ui.live_auto_totals['k_inputs']), (1, 0))
        self.assertEqual(self.ui.live_auto_totals['preparation_modeled_us'], p.modeled_action_us)
        rec = self.ui.live_action_records[-1]
        self.assertEqual((rec['semantic_input'], rec['phase'], rec['event_index']), ('UNFLAG', k.PHASE_PREPARATION, 8))
        self.ui.simple_auto_checkbox.setChecked(False)
        self.job.deliver_ack()
        self.assertEqual(rec['ack_state'], 'ACKED')
        self.assertEqual((self.ui._k_preparation_seq, self.ui._v1_input_seq, self.ui._k_m_revision), (1, 0, 1))
        self.assertEqual(len(self.job.requests), 2)
        self.assertEqual(self.ui.live_owner_records[-1]['preparation_input_count'], 1)

    def test_preparation_to_normal_k_records_actual_start_and_same_owner(self):
        self.arm()
        session = self.job.owner.session
        for index in range(2):
            if index:
                self.job.compute()
                self.tick()
            self.job.deliver_admission()
            self.job.deliver_ack()
        self.assertEqual((self.ui._k_phase, self.ui._v1_input_seq, self.ui._k_m_revision), (k.PHASE_K, 0, 1))
        owner = self.ui.live_owner_records[-1]
        self.assertEqual((owner['start_revision'], owner['k_start_revision'], owner['k_start_event_index']), (8, 10, 10))
        self.assertEqual(owner['k_start_cursor'], (4, 0))
        self.job.compute()
        self.assertIs(self.job.owner.session, session)
        self.assertFalse(self.job.pending.is_preparation)
        self.assertEqual(self.job.pending.pending_m_revision, 2)
        self.assertEqual(self.job.owner.decision.observation, self.job.pending.snapshot.observation)

    def test_preopen_flags_prepare_with_guess_off_then_wait(self):
        self.ui.on_right_click(8, 8)
        self.ui.simple_auto_checkbox.setChecked(True)
        self.job.compute()
        self.job.compute()
        self.tick()
        self.job.deliver_admission()
        self.job.deliver_ack()
        self.job.compute()
        self.assertTrue(self.job.pending.is_guess)
        self.assertFalse(self.job.pending.initial)
        self.assertFalse(self.ui.allow_guess_checkbox.isChecked())
        self.tick()
        self.assertEqual(self.ui._live_action_count, 2)
        self.assertEqual(len(self.job.validations), 1)
        self.assertEqual(self.ui.live_auto_totals['preparation_inputs'], 1)

    def test_pause_display_interval_and_new_nonce_reuse_bootstrap(self):
        p = self.arm()
        proof = self.job.owner.bootstrap_proof.analysis
        nonce = self.ui._k_validation_nonce
        self.ui.simple_auto_checkbox.setChecked(False)
        self.job.deliver_admission()
        with patch.object(KLocalSession, 'analyze_local', side_effect=AssertionError('repeat')):
            self.ui.probability_checkbox.setChecked(False)
            self.ui.auto_cursor_checkbox.setChecked(True)
            self.ui.simple_auto_interval_spin.setValue(1000)
            self.ui.on_analyze_current()
            self.ui.simple_auto_checkbox.setChecked(True)
            self.tick()
        self.assertIs(self.job.pending, p)
        self.assertIs(self.job.owner.bootstrap_proof.analysis, proof)
        self.assertNotEqual(self.ui._k_validation_nonce, nonce)
        self.job.deliver_admission()
        self.assertEqual(self.ui._live_action_count, 9)

    def test_history_only_tampering_blocks_preparation_before_token_consumption(self):
        for variant in ('revision', 'game', 'event', 'untracked'):
            with self.subTest(variant=variant):
                case = type(self)()
                case.setUp()
                try:
                    p = case.arm()
                    if variant == 'untracked':
                        case.engine.step(0, 0, Action.OPEN)
                    else:
                        key = {'revision': 'input_revision', 'game': 'game_id', 'event': 'event_index'}[variant]
                        case.ui.live_input_records[-1][key] = -1 if variant != 'game' else 'wrong'
                    self.assertEqual(case.ui._v1_snapshot(), p.snapshot)
                    with patch.object(case.engine, 'step', wraps=case.engine.step) as step:
                        case.job.deliver_admission()
                        step.assert_not_called()
                    self.assertEqual(case.job.applied, [])
                    self.assertEqual(len(case.ui._replay_recorder.events), 8)
                    self.assertTrue(case.ui._live_input_uncertain)
                finally:
                    case.doCleanups()

    def test_normal_manual_retire_restarts_fresh_bootstrap_after_cleanup(self):
        self.arm()
        old = self.job.owner
        self.job.deliver_admission()
        self.ui.simple_auto_checkbox.setChecked(False)
        self.job.deliver_ack()
        self.ui.on_right_click(5, 0)
        self.assertFalse(self.ui._k_retired)
        count = len(self.job.requests)
        self.ui.on_analyze_current()
        self.assertEqual(len(self.job.requests), count)
        self.job.complete_cancel()
        self.ui.on_analyze_current()
        self.assertIsNot(self.job.owner.session, old.session)
        self.assertEqual(self.job.requests[-1].entry_mode, k.FLAG_ADOPT)
        self.assertEqual(self.job.requests[-1].base_m, ())
        self.assertEqual(self.ui._replay_recorder.source_type, 'algorithm')

    def test_unconfirmed_preparation_ack_latches_all_policies_until_reset(self):
        self.arm()
        self.job.deliver_admission()
        self.ui._retire_v1_for_manual("manual handoff")
        self.job.complete_cancel()
        for policy in (POLICY_SIMPLE, POLICY_V1, POLICY_K):
            self.ui.live_policy_combo.setCurrentIndex(self.ui.live_policy_combo.findData(policy))
            self.ui.on_analyze_current()
            self.ui.simple_auto_checkbox.setChecked(True)
            self.assertTrue(self.ui._live_input_uncertain)
            self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
        self.assertEqual(self.ui.live_action_records[-1]['ack_state'], 'INCOMPLETE')
        self.ui.on_reset()
        self.assertEqual(self.ui._replay_recorder.source_type, 'human')
        self.assertIsNone(self.ui._k_bootstrap)

    def test_bootstrap_summary_substitution_at_gui_rejected(self):
        p = self.arm()
        b = replace(p.snapshot.bootstrap, proved_safe=(), unverified=p.snapshot.bootstrap.removable)
        self.ui._k_bootstrap = b
        self.job.deliver_admission()
        self.assertEqual(self.ui._live_action_count, 8)
        self.assertEqual(self.job.applied, [])
        self.assertTrue(self.ui._k_retired)

    def stopped(self, action):
        self.arm()
        if action == 'reset':
            self.ui.on_reset()
        elif action == 'replay':
            self.ui._enter_replay_mode(ReplayPlayer(self.ui._replay_recorder.to_replay_data()))
        elif action == 'policy':
            self.ui.live_policy_combo.setCurrentIndex(self.ui.live_policy_combo.findData(POLICY_SIMPLE))
        else:
            self.ui.close()
        count = self.ui._live_action_count
        self.job.deliver_admission()
        self.assertEqual(self.ui._live_action_count, count)
        self.assertEqual(self.job.applied, [])
        self.assertIsNone(self.ui._v1_pending)
        if action == 'replay':
            # Replay may show its existing Simple reference analysis.
            self.assertNotIn('K-P0', self.ui._analysis_result.status_text if self.ui._analysis_result else '')
        else:
            self.assertIsNone(self.ui._analysis_result)

    def test_late_preparation_after_reset(self):
        self.stopped('reset')

    def test_late_preparation_after_replay(self):
        self.stopped('replay')

    def test_late_preparation_after_policy_switch(self):
        self.stopped('policy')

    def test_late_preparation_after_close(self):
        self.stopped('close')

    def gesture(self, kind):
        self.arm()
        count = len(self.job.requests)
        self.ui.show()
        self.app.processEvents()
        self.ui.on_chord_mode_changed(ChordMode.BOTH_CLICK if kind == 'both' else ChordMode.LEFT_CLICK)
        target = self.ui._buttons[(0, 0) if kind == 'both' else (5, 0)]
        pos = self.ui.mapFromGlobal(target.mapToGlobal(target.rect().center()))
        native = self.ui.windowHandle()
        observations = []
        original = self.engine.step
        def step(*args):
            observations.append((self.ui._v1_owned, self.ui._v1_pending, self.ui._k_validation_nonce))
            return original(*args)
        with patch.object(self.engine, 'step', side_effect=step):
            button = Qt.RightButton if kind == 'right' else Qt.LeftButton
            QTest.mousePress(native, button, pos=pos)
            if kind == 'both':
                QTest.mousePress(native, Qt.RightButton, pos=pos)
            self.job.deliver_admission()
            self.job.complete_cancel()
            self.ui.on_analyze_current()
            self.assertEqual(len(self.job.requests), count)
            if kind == 'both':
                QTest.mouseRelease(native, Qt.RightButton, pos=pos)
            QTest.mouseRelease(native, button, pos=pos)
        self.assertEqual(observations, [(False, None, None)])
        self.assertEqual(self.ui._live_action_count, 9)
        self.assertFalse(self.ui._k_retired)
        self.assertEqual(self.ui._mouse_buttons, Qt.NoButton)

    def test_left_press_invalidates_before_original_input(self):
        self.gesture('left')

    def test_right_press_invalidates_before_original_input(self):
        self.gesture('right')

    def test_both_press_invalidates_before_original_chord(self):
        self.gesture('both')

    def test_three_preset_flagged_entry_gates_and_selection_only(self):
        for width, height, mines in ((9, 9, 10), (16, 16, 40), (30, 16, 99)):
            with self.subTest(size=(width, height)):
                engine = MinesweeperEngine(width, height, mines)
                ui = MinesweeperUI(engine)
                try:
                    layout = [(x, y) for y in range(height) for x in range(width) if (x, y) != (0, 0)][:mines]
                    with patch('core_engine.random.sample', return_value=layout):
                        ui.on_right_click(0, 0)
                    ui.live_policy_combo.setCurrentIndex(ui.live_policy_combo.findData(POLICY_K))
                    self.assertEqual(ui._v1_job.requests, [])
                    self.assertTrue(ui.analyze_button.isEnabled())
                    self.assertIsNone(ui._k_start_block_reason())
                    ui.on_analyze_current()
                    self.assertEqual(ui._v1_job.requests[-1].entry_mode, k.FLAG_ADOPT)
                    self.assertEqual(ui._live_action_count, 1)
                finally:
                    ui.close()
                    ui.deleteLater()
                    self.app.processEvents()

