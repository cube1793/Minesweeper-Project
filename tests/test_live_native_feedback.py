"""Native feedback regressions: deterministic owners, real UI input records."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest

from core_engine import Action
import live_k_policy as k
from live_policy import POLICY_SIMPLE, POLICY_V1, POLICY_K
from live_simple_preparation import prepare_flags
from live_flag_review import review_flags
from simple_algorithm import InconsistentObservationError
from tests.test_live_auto import LiveAutoUITests, recommendation
from tests.test_live_k_flag_adopt_ui import UI_MINES
from ui_manager import ChordMode

from tests.test_live_k_flag_adopt_ui import KFlagAdoptUITests


class KNativeFeedbackTests(unittest.TestCase):
    setUpClass = KFlagAdoptUITests.__dict__['setUpClass']
    setUp = KFlagAdoptUITests.setUp
    close_ui = KFlagAdoptUITests.close_ui
    tick = KFlagAdoptUITests.tick
    mixed = KFlagAdoptUITests.mixed
    arm = KFlagAdoptUITests.arm

    def test_manual_during_preparation_ack_finishes_original_input_then_readopts(self):
        self.arm()
        self.job.deliver_admission()
        old_session = self.job.owner.session
        record = self.ui.live_action_records[-1]
        self.ui.on_right_click(5, 0)
        self.assertFalse(self.ui._live_input_uncertain)
        self.assertFalse(self.ui._v1_owned)
        requests = len(self.job.requests)
        self.job.deliver_ack()
        self.assertEqual(record['ack_state'], 'ACKED')
        self.assertEqual(len(self.job.requests), requests)
        self.assertEqual(self.ui._v1_cursor, (5, 0))
        self.assertEqual(self.ui._k_base_m, ())
        self.job.complete_cancel()
        self.ui.on_analyze_current()
        self.assertIsNot(self.job.owner.session, old_session)
        self.assertEqual(self.job.requests[-1].input_revision, 10)

    def arm_mode(self, mode):
        if mode == 'preparation':
            self.arm()
        else:
            if mode == 'adopt':
                self.ui.on_left_click(0, 0)
            self.ui.simple_auto_checkbox.setChecked(True)
            self.job.compute()
            self.ui.allow_guess_checkbox.setChecked(True)
            self.tick()

    def test_ack_window_all_entries_and_manual_gestures_preserves_current_state(self):
        for mode in ('canonical', 'adopt', 'preparation'):
            for gesture in ('left', 'right', 'both'):
                with self.subTest(mode=mode, gesture=gesture):
                    case = type(self)()
                    case.setUp()
                    try:
                        case.arm_mode(mode)
                        case.job.deliver_admission()
                        count = case.ui._live_action_count
                        method = {'left': case.ui.on_left_click, 'right': case.ui.on_right_click,
                                  'both': case.ui.on_both_click}[gesture]
                        method(0, 0) if gesture == 'both' else method(5, 0)
                        self.assertEqual(case.ui._live_action_count, count + 1)
                        current = (case.engine.get_observation(), case.ui._v1_cursor, case.ui._live_action_count)
                        requests = len(case.job.requests)
                        case.job.deliver_ack()
                        self.assertEqual((case.engine.get_observation(), case.ui._v1_cursor,
                                          case.ui._live_action_count), current)
                        self.assertEqual(len(case.job.requests), requests)
                        self.assertEqual(case.ui._k_base_m, ())
                        self.assertFalse(case.ui._live_input_uncertain)
                        case.job.complete_cancel()
                        self.assertTrue(case.ui.analyze_button.isEnabled())
                    finally:
                        case.doCleanups()

    def test_first_press_revokes_before_release_and_no_new_owner_while_held(self):
        for gesture in ('left', 'right', 'both'):
            with self.subTest(gesture=gesture):
                case = type(self)()
                case.setUp()
                try:
                    case.arm()
                    case.job.deliver_admission()
                    case.ui.show()
                    case.app.processEvents()
                    case.ui.on_chord_mode_changed(ChordMode.BOTH_CLICK if gesture == 'both' else ChordMode.LEFT_CLICK)
                    target = case.ui._buttons[(0, 0) if gesture == 'both' else (5, 0)]
                    pos = case.ui.mapFromGlobal(target.mapToGlobal(target.rect().center()))
                    native = case.ui.windowHandle()
                    count, requests = case.ui._live_action_count, len(case.job.requests)
                    button = Qt.RightButton if gesture == 'right' else Qt.LeftButton
                    QTest.mousePress(native, button, pos=pos)
                    if gesture == 'both':
                        QTest.mousePress(native, Qt.RightButton, pos=pos)
                    self.assertFalse(case.ui._v1_owned)
                    case.job.deliver_ack()
                    case.job.complete_cancel()
                    case.ui.simple_auto_checkbox.setChecked(True)
                    case.ui.on_analyze_current()
                    self.assertEqual(len(case.job.requests), requests)
                    if gesture == 'both':
                        QTest.mouseRelease(native, Qt.RightButton, pos=pos)
                    QTest.mouseRelease(native, button, pos=pos)
                    self.assertEqual(case.ui._live_action_count, count + 1)
                    self.assertFalse(case.ui._live_input_uncertain)
                finally:
                    case.doCleanups()

    def test_multiple_manual_inputs_do_not_overwrite_sealed_ack(self):
        self.arm()
        self.job.deliver_admission()
        for x in (5, 6, 5, 6):
            self.ui.on_right_click(x, 0)
        self.job.deliver_ack()
        self.job.complete_cancel()
        self.assertEqual(self.ui._live_action_count, 13)
        self.assertFalse(self.ui._k_retired)
        self.assertEqual(self.ui._replay_recorder.source_type, 'algorithm')

    def test_policy_switch_drains_original_ack_without_next(self):
        self.arm()
        self.job.deliver_admission()
        requests = len(self.job.requests)
        self.ui.live_policy_combo.setCurrentIndex(self.ui.live_policy_combo.findData(POLICY_SIMPLE))
        self.assertIsNotNone(self.ui._k_retiring)
        self.job.deliver_ack()
        self.assertEqual(len(self.job.requests), requests)
        self.job.complete_cancel()
        self.assertFalse(self.ui._live_input_uncertain)
        self.assertTrue(self.ui.analyze_button.isEnabled())

    def test_duplicate_or_forged_retiring_ack_is_fail_closed(self):
        for variant in ('duplicate', 'forged'):
            with self.subTest(variant=variant):
                case = type(self)()
                case.setUp()
                try:
                    case.arm()
                    case.job.deliver_admission()
                    case.ui.on_right_click(5, 0)
                    ack = case.job.acks[-1]
                    if variant == 'duplicate':
                        case.job.deliver_ack()
                    else:
                        ack = replace(ack, permit=replace(ack.permit, nonce='f' * 32))
                    case.job.acknowledged.emit(ack)
                    self.assertTrue(case.ui._live_input_uncertain)
                    self.assertFalse(case.ui.allow_guess_checkbox.isChecked())
                finally:
                    case.doCleanups()

    def test_history_mutation_during_retirement_is_rejected(self):
        self.arm()
        self.job.deliver_admission()
        self.ui.on_right_click(5, 0)
        self.ui.live_input_records[-2]['event_index'] = -1
        self.job.deliver_ack()
        self.assertTrue(self.ui._live_input_uncertain)
        self.assertIn('이력', self.ui.live_policy_status_label.text())

    def test_timeout_and_cleanup_failure_latch_preserves_first_cause(self):
        for error in ('ACK_TIMEOUT', 'CLEANUP_FAILURE'):
            with self.subTest(error=error):
                case = type(self)()
                case.setUp()
                try:
                    case.arm()
                    case.job.deliver_admission()
                    case.ui.on_right_click(5, 0)
                    if error == 'CLEANUP_FAILURE':
                        case.job.deliver_ack()
                    run = case.job.active_run_id
                    case.job.state = 'idle'
                    case.job.active_run_id = None
                    case.job.finished.emit(dict(run_id=run, policy_id=POLICY_K, status='FAILED',
                        error=error, cleanup_complete=True, reaped=True, tree_active_count=0))
                    for policy in (POLICY_SIMPLE, POLICY_V1, POLICY_K):
                        case.ui.live_policy_combo.setCurrentIndex(case.ui.live_policy_combo.findData(policy))
                        case.ui.simple_auto_checkbox.setChecked(True)
                        self.assertFalse(case.ui.simple_auto_checkbox.isChecked())
                        self.assertIn(error, case.ui.live_policy_status_label.text())
                    self.assertEqual(case.ui._live_first_failure['cause'], error)
                finally:
                    case.doCleanups()

    def test_pause_keeps_guess_manual_and_failure_clear_it(self):
        self.arm()
        proposal = self.job.pending
        self.ui.allow_guess_checkbox.setChecked(True)
        self.ui.simple_auto_checkbox.setChecked(False)
        self.assertTrue(self.ui.allow_guess_checkbox.isChecked())
        self.ui.simple_auto_checkbox.setChecked(True)
        self.assertIs(self.job.pending, proposal)
        self.ui.on_right_click(5, 0)
        self.assertFalse(self.ui.allow_guess_checkbox.isChecked())
        self.assertFalse(self.ui.simple_auto_checkbox.isChecked())

    def test_terminal_exact_receipt_clears_pending_without_false_latch(self):
        self.ui._rebuild_game(2, 1, 1)
        with patch.object(self.ui, '_v1_supported', return_value=True), \
                patch('core_engine.random.sample', return_value=[(1, 0)]):
            self.ui.simple_auto_checkbox.setChecked(True)
            self.job.compute()
            self.tick()
            self.job.deliver_admission()
            ack = self.job.acks[-1]
            self.assertEqual(ack.status, 'WON')
            self.job.owner.acknowledge(ack)
            self.job.state = 'idle'
            self.job.active_run_id = None
            self.job.finished.emit(dict(run_id=ack.run_id, policy_id=POLICY_K, status='SUCCEEDED',
                cleanup_complete=True, reaped=True, tree_active_count=0, last_k_ack=k.to_dict(ack)))
        self.assertIsNone(self.ui._v1_expected_ack)
        self.ui.live_policy_combo.setCurrentIndex(self.ui.live_policy_combo.findData(POLICY_SIMPLE))
        self.ui.live_policy_combo.setCurrentIndex(self.ui.live_policy_combo.findData(POLICY_K))
        self.assertFalse(self.ui._live_input_uncertain)
        self.assertIn('게임 종료', self.ui.live_policy_status_label.text())


class SimplePreparationProofTests(unittest.TestCase):
    def test_public_mixed_partition_matches_unchanged_v1_scope(self):
        for observation, count in ((((1, -3, -2, -2, 0, -3, -2, -3),), 2),
                                   (((-3, 1, -2),), 1), (((-3, -3),), 0),
                                   (((1, -3, -3),), 2)):
            with self.subTest(observation=observation):
                result = prepare_flags(observation, count)
                v1 = review_flags(observation, count)
                self.assertEqual(result.retained, v1.proved_mine)
                self.assertEqual(result.removable, v1.removable)
                self.assertEqual(result.proved_safe, v1.proved_safe)

    def test_custom_maximum_and_exact_prefix_without_widening_v1(self):
        grid = [[-2] * 100 for _ in range(100)]
        grid[0][0] = grid[99][99] = -3
        result = prepare_flags(grid, 100)
        self.assertEqual(result.removable, ((0, 0), (99, 99)))
        self.assertEqual(result.target(1, result.observation_after(1)), (99, 99))
        with self.assertRaises(ValueError):
            result.target(0, result.observation_after(1))
        with self.assertRaises(ValueError):
            review_flags(grid, 100)

    def test_contradiction_and_forged_observation_are_not_all_unknown(self):
        for grid, count in ((((0, -3, 1),), 1), (((3, -3),), 1), (((-3, True),), 1)):
            with self.subTest(grid=grid), self.assertRaises((ValueError, InconsistentObservationError)):
                prepare_flags(grid, count)


class SimplePreparationUITests(unittest.TestCase):
    setUpClass = LiveAutoUITests.__dict__['setUpClass']
    setUp = LiveAutoUITests.setUp
    close_ui = LiveAutoUITests.close_ui
    tick = LiveAutoUITests.tick

    def mixed(self):
        self.ui._rebuild_game(5, 1, 2)
        self.engine.reset_with_mines(5, 1, 2, {(1, 0), (4, 0)})
        for x in (0, 2):
            self.ui.on_left_click(x, 0)
        for x in (1, 3, 4):
            self.ui.on_right_click(x, 0)

    def test_mixed_flags_exact_events_cost_and_nonhuman_then_normal_win(self):
        self.mixed()
        self.ui.on_analyze_current()
        self.assertEqual(self.ui._simple_preparation.retained, ((1, 0),))
        self.assertEqual(self.ui._replay_recorder.source_type, 'human')
        self.assertEqual(len(self.ui._replay_recorder.events), 5)
        self.ui.simple_auto_checkbox.setChecked(True)
        for x in (3, 4):
            before = self.ui._live_action_count
            self.tick()
            self.assertEqual(self.ui._live_action_count, before + 1)
            record = self.ui.live_action_records[-1]
            self.assertEqual((record['x'], record['semantic_input']), (x, 'UNFLAG'))
            self.assertTrue(record['actual_input_confirmed'])
            self.assertGreater(record['modeled_action_us'], 0)
            self.assertEqual(self.engine.get_observation()[0][1], -3)
        self.assertEqual(self.ui.live_auto_totals['preparation_inputs'], 2)
        self.assertEqual(self.ui._replay_recorder.source_type, 'algorithm')
        self.tick()
        self.assertEqual(self.engine.status.name, 'WON')
        self.assertEqual(len(self.ui._replay_recorder.events), 8)

    def test_all_flagged_before_open_prepares_without_guess(self):
        for y in range(3):
            for x in range(3):
                self.ui.on_right_click(x, y)
        self.ui.simple_auto_checkbox.setChecked(True)
        for index in range(9):
            self.tick()
            self.assertEqual(self.ui._live_action_count, 10 + index)
            self.assertFalse(self.ui.allow_guess_checkbox.isChecked())
        self.assertEqual(self.ui._simple_preparation_seq, 9)
        self.assertFalse(self.ui._analysis_first_click)
        self.assertIsNotNone(self.ui._analysis_result.decision)
        self.assertFalse(self.ui._simple_auto_pending)
        self.assertEqual([e.action for e in self.ui._replay_recorder.events], ['FLAG'] * 18)

    def test_pause_toggles_keep_epoch_and_manual_change_starts_new_one(self):
        self.mixed()
        self.ui.simple_auto_checkbox.setChecked(True)
        epoch = self.ui._simple_preparation
        self.ui.allow_guess_checkbox.setChecked(True)
        self.ui.simple_auto_checkbox.setChecked(False)
        with patch('ui_manager.prepare_flags', side_effect=AssertionError('repeat review')):
            self.ui.probability_checkbox.setChecked(False)
            self.ui.simple_auto_interval_spin.setValue(0)
            self.ui.simple_auto_checkbox.setChecked(True)
            self.assertTrue(self.ui.allow_guess_checkbox.isChecked())
            self.assertIs(self.ui._simple_preparation, epoch)
            self.tick()
        self.ui.on_right_click(3, 0)
        self.assertFalse(self.ui.allow_guess_checkbox.isChecked())
        self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
        self.assertIsNot(self.ui._simple_preparation, epoch)
        self.assertEqual(self.ui._simple_preparation_seq, 0)

    def test_stale_candidate_history_nonce_and_forged_target_never_input(self):
        for variant in ('history', 'nonce', 'target', 'observation'):
            with self.subTest(variant=variant):
                case = type(self)()
                case.setUp()
                try:
                    case.mixed()
                    case.ui.simple_auto_checkbox.setChecked(True)
                    callback = case.ui._simple_auto_timeout_slot
                    if variant == 'history':
                        case.ui.live_input_records[-1]['event_index'] = -1
                    elif variant == 'nonce':
                        case.ui.simple_auto_checkbox.setChecked(False)
                    elif variant == 'observation':
                        case.engine.step(4, 0, Action.FLAG)
                    else:
                        case.ui._analysis_result = replace(case.ui._analysis_result,
                            move=replace(case.ui._analysis_result.move, x=1))
                    with patch.object(case.engine, 'step') as step:
                        callback()
                        callback()
                    step.assert_not_called()
                finally:
                    case.doCleanups()

    def test_own_automatic_flag_never_triggers_unflag_loop(self):
        self.ui._rebuild_game(5, 1, 2)
        self.engine.reset_with_mines(5, 1, 2, {(1, 0), (4, 0)})
        self.ui.on_left_click(0, 0)
        self.ui.on_left_click(2, 0)
        with patch('ui_manager.analyze_position', return_value=recommendation(Action.FLAG, 1, 0)):
            self.ui.simple_auto_checkbox.setChecked(True)
        with patch('ui_manager.prepare_flags', side_effect=AssertionError('own flag re-reviewed')):
            self.tick()
        self.assertEqual(self.engine.get_observation()[0][1], -3)
        self.assertEqual(self.ui.live_auto_totals['preparation_inputs'], 0)
        self.assertEqual(self.ui._analysis_result.move.action, Action.OPEN)

    def test_zero_removals_preserves_confirmed_flag_without_input_cost(self):
        self.mixed()
        self.ui.on_right_click(3, 0)
        self.ui.on_right_click(4, 0)
        self.ui.on_analyze_current()
        self.assertEqual(self.ui._simple_preparation.removable, ())
        self.assertEqual(self.ui._analysis_result.move.action, Action.OPEN)
        self.assertEqual(self.ui.live_auto_totals['preparation_inputs'], 0)

    def test_custom_ui_preparation_keeps_range_and_marks_unavailable_cost(self):
        self.ui._rebuild_game(31, 17, 1)
        self.ui.on_right_click(0, 0)
        self.ui.on_right_click(30, 16)
        self.ui.simple_auto_checkbox.setChecked(True)
        self.tick()
        record = self.ui.live_action_records[-1]
        self.assertEqual((record['x'], record['y']), (0, 0))
        self.assertIsNone(record['modeled_action_us'])
        self.assertEqual(record['modeled_cost_status'], 'OUTSIDE_FROZEN_TABLE')
        self.assertEqual(self.engine.get_observation()[0][0], -2)

    def test_preparation_step_and_replay_failures_never_retry(self):
        for stage in ('step', 'replay'):
            with self.subTest(stage=stage):
                case = type(self)()
                case.setUp()
                try:
                    case.mixed()
                    case.ui.simple_auto_checkbox.setChecked(True)
                    target = case.engine if stage == 'step' else case.ui
                    method = 'step' if stage == 'step' else '_record_replay_event'
                    with patch.object(target, method, side_effect=RuntimeError('fixture ' + stage)) as failed:
                        case.tick()
                        case.tick()
                    failed.assert_called_once()
                    self.assertFalse(case.ui.simple_auto_checkbox.isChecked())
                    self.assertFalse(case.ui.allow_guess_checkbox.isChecked())
                    if stage == 'replay':
                        self.assertEqual(case.ui._replay_recorder.source_type, 'algorithm')
                    self.assertTrue(case.ui._live_input_uncertain)
                    case.ui.simple_auto_checkbox.setChecked(True)
                    self.assertFalse(case.ui.simple_auto_checkbox.isChecked())
                finally:
                    case.doCleanups()

    def test_pending_preparation_expired_by_reset_policy_replay_close(self):
        from replay_model import ReplayBoard, ReplayData
        from replay_player import ReplayPlayer
        for transition in ('reset', 'policy', 'replay', 'close'):
            with self.subTest(transition=transition):
                case = type(self)()
                case.setUp()
                try:
                    case.mixed()
                    case.ui.simple_auto_checkbox.setChecked(True)
                    callback = case.ui._simple_auto_timeout_slot
                    if transition == 'reset':
                        case.ui.on_reset()
                    elif transition == 'policy':
                        case.ui.live_policy_combo.setCurrentIndex(case.ui.live_policy_combo.findData(POLICY_V1))
                    elif transition == 'replay':
                        case.ui._enter_replay_mode(ReplayPlayer(ReplayData(ReplayBoard(5, 1, 2, {(1, 0), (4, 0)}), ())))
                    else:
                        case.ui.close()
                    with patch.object(case.engine, 'step') as step:
                        callback()
                    step.assert_not_called()
                    self.assertIsNone(case.ui._simple_preparation)
                finally:
                    case.doCleanups()

