"""Same-layout history and Replay return; real Qt/engine, fake worker only."""
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from PyQt5 import sip
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from core_engine import GameStatus, MinesweeperEngine
import live_k_policy as k
from live_policy import FIXED_BOARD, POLICY_SIMPLE, POLICY_V1, plan_snapshot, make_ack
from live_same_board import FixedLayout
from replay_json import replay_data_to_dict
from replay_model import ReplayBoard, ReplayData, ReplayEvent, SOURCE_ALGORITHM, SOURCE_HUMAN
from replay_player import ReplayPlayer
from tests.test_live_auto import advance_auto_timer
from tests.test_live_same_board_ui import MixedFakeJob
from tests.ui_settings import isolate_ui_settings
from ui_manager import DIFFICULTY_PRESETS, MinesweeperUI


class SameBoardHistoryUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.settings = isolate_ui_settings(self)
        self.uis = []
        for target in ('_ensure_zini_metric_job',):
            p = patch.object(MinesweeperUI, target, return_value=None)
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.close_all)

    def close_all(self):
        for ui in self.uis:
            ui.same_board_history_menu.close()
            ui._stop_replay_autoplay()
            ui.close()
            ui.deleteLater()
        self.app.processEvents()

    def make_ui(self, policy=POLICY_SIMPLE, layout=None):
        layout = layout or FixedLayout(5, 1, 1, {(2, 0)})
        with patch('ui_manager.LivePolicyJob', MixedFakeJob):
            ui = MinesweeperUI(MinesweeperEngine(layout.width, layout.height, layout.num_mines))
        self.uis.append(ui)
        ui.live_policy_combo.setCurrentIndex(ui.live_policy_combo.findData(policy))
        ui.on_reset()
        layout.reset_engine(ui.engine)
        return ui

    def finish(self, ui):
        mine = next(iter(ui.engine.get_board_snapshot().mines))
        ui.on_left_click(*mine)
        self.assertEqual(ui.engine.status, GameStatus.LOST)

    def activate(self, ui):
        self.finish(ui)
        ui.on_same_board_retry()
        self.assertEqual(len(ui._same_board_completed_games), 1)
        self.assertTrue(ui.same_board_history_button.isEnabled())
        return ui._same_board_completed_games[0]

    def assert_empty_group(self, ui):
        self.assertIsNone(ui._same_board_history_layout)
        self.assertEqual(ui._same_board_completed_games, [])
        self.assertEqual(ui.same_board_history_menu.actions(), [])
        self.assertFalse(ui.same_board_history_button.isEnabled())

    def assert_fresh_fixed(self, ui, layout, previous_id, previous_generation):
        self.assertFalse(ui._replay_mode)
        self.assertTrue(layout.matches(ui.engine.get_board_snapshot()))
        self.assertNotEqual(ui._live_game_id, previous_id)
        self.assertGreater(ui._live_board_generation, previous_generation)
        self.assertTrue(ui._fixed_board_start())
        self.assertEqual(ui._live_fixed_origin.layout, layout)
        self.assertFalse(ui._live_fresh_reset)
        self.assertFalse(ui._k_reset_ready)
        self.assertEqual(ui._live_action_count, 0)
        self.assertEqual(ui.live_input_records, [])
        self.assertEqual(ui.live_action_records, [])
        self.assertEqual(ui.live_owner_records, [])
        self.assertTrue(all(v == 0 for v in ui.live_auto_totals.values()))
        self.assertEqual(ui.engine.get_counter_snapshot()['active_clicks'], 0)
        self.assertEqual(ui.engine.get_counter_snapshot()['wasted_clicks'], 0)
        self.assertEqual(ui.engine.get_elapsed_time(), 0)
        self.assertEqual(ui._replay_recorder.events, ())
        self.assertEqual(ui._replay_recorder.source_type, SOURCE_HUMAN)
        self.assertEqual(FixedLayout.from_replay_board(ui._replay_recorder.board), layout)
        self.assertEqual(ui._v1_cursor, (0, 0))
        self.assertEqual(ui._k_base_m, ())
        self.assertEqual(ui._k_m_revision, 0)
        self.assertIsNone(ui._k_validation_nonce)
        self.assertIsNone(ui._v1_expected_ack)
        self.assertIsNone(ui._v1_pending)
        self.assertIsNone(ui._k_deferred_permit)
        self.assertIsNone(ui._certainty_frame)
        self.assertIsNone(ui._fixed_cadence)
        self.assertIsNone(ui.auto_cursor_overlay._reservation)
        self.assertFalse(ui.auto_cursor_overlay._available)
        self.assertFalse(ui.simple_auto_checkbox.isChecked())
        self.assertFalse(ui.allow_guess_checkbox.isChecked())
        self.assertEqual(ui._normal_game_config, (layout.width, layout.height, layout.num_mines))
        label = next((n for n, config in DIFFICULTY_PRESETS.items() if config == ui._normal_game_config), '커스텀')
        self.assertEqual(ui.difficulty_combo.currentText(), label)
        self.assertEqual(len(ui._buttons), layout.width*layout.height)

    def assert_fresh_canonical(self, ui, config, previous_id, previous_generation):
        from live_policy import CANONICAL_NEW
        self.assertFalse(ui._replay_mode)
        self.assertNotEqual(ui._live_game_id, previous_id)
        self.assertGreater(ui._live_board_generation, previous_generation)
        self.assertEqual((ui.engine.width, ui.engine.height, ui.engine.num_mines), config)
        self.assertEqual(ui._normal_game_config, config)
        self.assertFalse(ui.engine.get_board_snapshot().mines_placed)
        self.assertEqual(ui.engine.get_board_snapshot().mines, frozenset())
        self.assertIsNone(ui._live_fixed_origin)
        self.assertFalse(ui._fixed_board_start())
        self.assertTrue(ui._live_fresh_reset)
        self.assertTrue(ui._k_reset_ready)
        self.assertEqual(ui._v1_entry_mode, CANONICAL_NEW)
        self.assertEqual(ui._live_action_count, 0)
        self.assertEqual(ui.live_input_records, [])
        self.assertEqual(ui.live_action_records, [])
        self.assertEqual(ui.live_owner_records, [])
        self.assertTrue(all(value == 0 for value in ui.live_auto_totals.values()))
        self.assertEqual(ui._replay_recorder.events, ())
        self.assertIsNone(ui._replay_recorder.board)
        self.assertEqual(ui._replay_recorder.source_type, SOURCE_HUMAN)
        self.assertEqual(ui.engine.get_elapsed_time(), 0)
        counters = ui.engine.get_counter_snapshot()
        self.assertEqual(counters['active_clicks'] + counters['wasted_clicks'], 0)
        self.assertEqual(ui._v1_cursor, (0, 0))
        self.assertEqual(ui._k_base_m, ())
        self.assertEqual(ui._k_m_revision, 0)
        self.assertIsNone(ui._k_validation_nonce)
        self.assertIsNone(ui._v1_expected_ack)
        self.assertIsNone(ui._v1_pending)
        self.assertIsNone(ui._certainty_frame)
        self.assertIsNone(ui._fixed_cadence)
        self.assertIsNone(ui.auto_cursor_overlay._reservation)
        self.assertFalse(ui.simple_auto_checkbox.isChecked())
        self.assertFalse(ui.allow_guess_checkbox.isChecked())
        self.assertTrue(all(v == -2 for row in ui.engine.get_observation() for v in row))
        self.assert_empty_group(ui)
        label = next((name for name, dims in DIFFICULTY_PRESETS.items() if dims == config), '커스텀')
        self.assertEqual(ui.difficulty_combo.currentText(), label)
        self.assertEqual(len(ui._buttons), config[0] * config[1])

    def save_fixture(self, data, name='replay.json'):
        path = Path(self.settings.fileName()).parent/name
        path.write_text(json.dumps(replay_data_to_dict(data)), encoding='utf-8')
        return path

    def load(self, ui, path):
        with patch('ui_manager.QFileDialog.getOpenFileName', return_value=(str(path), 'JSON')):
            ui.on_load_replay()

    def test_t1_activation_menu_current_completion_and_game_id_dedup(self):
        ui = self.make_ui()
        self.assert_empty_group(ui)
        self.finish(ui)
        first_id = ui._live_game_id
        ui.same_board_history_menu.aboutToShow.emit()
        self.assert_empty_group(ui)
        ui.on_same_board_retry()
        self.assertEqual([g.game_id for g in ui._same_board_completed_games], [first_id])
        self.finish(ui)
        second_id = ui._live_game_id
        for _ in range(3):
            ui.same_board_history_menu.aboutToShow.emit()
        self.assertEqual([g.game_id for g in ui._same_board_completed_games], [first_id, second_id])
        self.assertEqual(len(ui.same_board_history_menu.actions()), 2)
        ui.on_same_board_retry()
        self.assertEqual(len(ui._same_board_completed_games), 2)
        self.finish(ui)
        third_id = ui._live_game_id
        ui.on_view_current_replay()
        self.assertEqual([g.game_id for g in ui._same_board_completed_games], [first_id, second_id, third_id])
        current = ui._same_board_completed_games[-1]
        for _ in range(3):
            ui._view_completed_live_game(current)
            ui.same_board_history_menu.aboutToShow.emit()
        self.assertEqual(len(ui._same_board_completed_games), 3)

    def test_t2_progress_excluded_distinct_attempts_and_detached_source_evidence(self):
        ui = self.make_ui()
        first = self.activate(ui)
        frozen = (first.replay, first.evidence_json, first.layout)
        ui.on_left_click(0, 0)
        self.assertEqual(ui.engine.status, GameStatus.PLAYING)
        ui.same_board_history_menu.aboutToShow.emit()
        self.assertEqual(len(ui._same_board_completed_games), 1)
        ui._view_completed_live_game(first)
        ui.on_same_board_retry()  # This test continues the same archived layout.
        self.assertEqual(len(ui._same_board_completed_games), 1)
        ui._replay_recorder.source_type = SOURCE_ALGORITHM  # Provenance fixture only.
        self.finish(ui)
        ui.same_board_history_menu.aboutToShow.emit()
        second = ui._same_board_completed_games[1]
        self.assertNotEqual(first.game_id, second.game_id)
        self.assertEqual(first.replay.source_type, SOURCE_HUMAN)
        self.assertEqual(second.replay.source_type, SOURCE_ALGORITHM)
        self.assertEqual(len(json.loads(first.evidence_json)['inputs']), 1)
        self.assertEqual(len(json.loads(second.evidence_json)['inputs']), 1)
        ui.on_same_board_retry()
        self.finish(ui)
        ui.same_board_history_menu.aboutToShow.emit()
        self.assertEqual(len(ui._same_board_completed_games), 3)
        self.assertEqual((first.replay, first.evidence_json, first.layout), frozen)

    def test_t3_new_game_boundaries_clear_actions_and_reject_old_callbacks(self):
        for boundary in ('smile', 'space', 'return', 'policy_new', 'difficulty', 'rebuild'):
            with self.subTest(boundary=boundary):
                ui = self.make_ui()
                old = self.activate(ui)
                action = ui.same_board_history_menu.actions()[0]
                if boundary == 'smile':
                    ui.reset_button.click()
                elif boundary in ('space', 'return'):
                    ui._on_game_shortcut(Qt.Key_Space if boundary == 'space' else Qt.Key_Return)
                elif boundary == 'policy_new':
                    ui.live_policy_new_game_button.click()
                elif boundary == 'difficulty':
                    ui.on_difficulty_changed('초급 (9x9, 10)')
                else:
                    ui._rebuild_game(5, 1, 1)
                self.assert_empty_group(ui)
                self.assertFalse(ui.engine.get_board_snapshot().mines_placed)
                ui._view_completed_live_game(old)
                if not sip.isdeleted(action):
                    action.trigger()
                self.assertFalse(ui._replay_mode)
                # Even an accidental identical next layout cannot revive the cleared group.
                old.layout.reset_engine(ui.engine)
                ui.same_board_history_menu.aboutToShow.emit()
                self.assert_empty_group(ui)

    def test_t4_all_replay_entry_routes_default_to_canonical_at_every_index(self):
        for route in ('current', 'history', 'file'):
            for index in (0, 1, 2):
                with self.subTest(route=route, index=index):
                    ui = self.make_ui()
                    if route == 'history':
                        self.activate(ui)
                    ui.on_left_click(0, 0)
                    self.finish(ui)
                    data = ui._build_current_replay_data('fixture', require_finished=True)
                    target = FixedLayout.from_replay_board(data.board)
                    prior, generation = ui._live_game_id, ui._live_board_generation
                    if route == 'current':
                        ui.on_view_current_replay()
                    elif route == 'history':
                        # Choosing an old record must first preserve the current completed attempt.
                        ui._view_completed_live_game(ui._same_board_completed_games[0])
                        self.assertEqual(len(ui._same_board_completed_games), 2)
                        ui._view_completed_live_game(ui._same_board_completed_games[-1])
                    else:
                        self.load(ui, self.save_fixture(data))
                    ui._replay_player.go_to(index)
                    ui._refresh_replay_view_after_move()
                    if index == 1:
                        ui.on_replay_play_pause()
                        self.assertTrue(ui._replay_autoplay_timer.isActive())
                    with patch.object(ui, '_ask_custom_dimensions', side_effect=AssertionError('No return modal')):
                        self.assertTrue(ui._exit_replay_mode())
                    self.assertFalse(ui._replay_autoplay_timer.isActive())
                    self.assert_fresh_canonical(ui, (target.width, target.height, target.num_mines), prior, generation)
                    self.assert_empty_group(ui)

    def test_t4_foreign_preset_custom_and_incomplete_replay_config_and_gates(self):
        for dims in ((9, 9, 10), (16, 16, 40), (30, 16, 99), (6, 2, 2)):
            with self.subTest(dims=dims):
                ui = self.make_ui(POLICY_V1)
                mines = {(n % dims[0], n // dims[0]) for n in range(dims[2])}
                target = FixedLayout(*dims, mines)
                data = ReplayData(ReplayBoard(*dims, mines), (ReplayEvent(.1, 0, 0, 'FLAG'),))
                old, generation = ui._live_game_id, ui._live_board_generation
                self.load(ui, self.save_fixture(data))
                ui._replay_player.go_to(1)
                self.assertEqual(ui._replay_player.engine.status, GameStatus.PLAYING)
                with patch.object(ui, '_ask_custom_dimensions', side_effect=AssertionError('No return modal')):
                    self.assertTrue(ui._exit_replay_mode())
                self.assert_fresh_canonical(ui, dims, old, generation)
                self.assert_empty_group(ui)
                self.assertEqual(ui._v1_supported(), dims != (6, 2, 2))
                self.assertEqual(ui.simple_auto_checkbox.isEnabled(), dims != (6, 2, 2))
                if dims == (6, 2, 2):
                    ui.live_policy_combo.setCurrentIndex(ui.live_policy_combo.findData(POLICY_SIMPLE))
                    self.assertTrue(ui.simple_auto_checkbox.isEnabled())

    def test_t5_load_cancel_invalid_same_and_different_layouts(self):
        ui = self.make_ui()
        old = self.activate(ui)
        group = ui._same_board_history_layout
        self.load(ui, '')
        self.assertFalse(ui._replay_mode)
        self.assertIs(ui._same_board_completed_games[0], old)
        invalid = Path(self.settings.fileName()).parent/'invalid.json'
        invalid.write_text('{bad JSON', encoding='utf-8')
        with patch('ui_manager.QMessageBox.warning') as warning:
            self.load(ui, invalid)
        warning.assert_called_once()
        self.assertEqual(ui._same_board_history_layout, group)
        same = self.save_fixture(old.replay)
        for _ in range(2):
            self.load(ui, same)
            self.assertEqual(ui._same_board_completed_games, [old])
        ui.on_same_board_retry()  # Explicit history-preserving choice.
        self.assertEqual(ui._same_board_completed_games, [old])
        other = ReplayData(ReplayBoard(5, 1, 1, {(4, 0)}), ())
        self.load(ui, self.save_fixture(other, 'other.json'))
        self.assert_empty_group(ui)
        ui._view_completed_live_game(old)
        self.assertEqual(ui._replay_player.replay_data, other)
        previous, generation = ui._live_game_id, ui._live_board_generation
        ui._exit_replay_mode()
        self.assert_fresh_canonical(ui, (5, 1, 1), previous, generation)
        self.assert_empty_group(ui)

    def test_t5_same_layout_policy_speed_display_and_replay_keep_group(self):
        ui = self.make_ui()
        old = self.activate(ui)
        for policy in (POLICY_V1, k.POLICY_K, k.POLICY_K_LC0, k.POLICY_K_LC1, POLICY_SIMPLE):
            ui.live_policy_combo.setCurrentIndex(ui.live_policy_combo.findData(policy))
            ui.probability_checkbox.toggle()
            ui.auto_cursor_checkbox.toggle()
            ui.simple_auto_interval_spin.setValue(250)
            self.assertEqual(ui._same_board_completed_games, [old])
        for _ in range(2):
            ui._view_completed_live_game(old)
            ui.on_same_board_retry()
            self.assertEqual(ui._same_board_completed_games, [old])

    def test_t6_return_public_guess_and_stale_proposal_permit_ack_all_worker_policies(self):
        for policy in (POLICY_V1, k.POLICY_K, k.POLICY_K_LC0, k.POLICY_K_LC1):
            with self.subTest(policy=policy):
                ui = self.make_ui(policy)
                old = self.activate(ui)
                ui._v1_supported = lambda: True  # Explicit 5x1 public-policy seam, never production preset evidence.
                ui._view_completed_live_game(old)
                self.assertTrue(ui.on_same_board_retry())
                ui.simple_auto_checkbox.setChecked(True)
                job = ui._v1_job
                if policy == POLICY_V1:
                    job.deliver(plan_snapshot(job.requests[-1]))
                else:
                    job.compute()
                proposal = job.pending
                self.assertEqual(proposal.snapshot.entry_mode, FIXED_BOARD)
                self.assertEqual(proposal.snapshot.input_revision, 0)
                self.assertTrue(proposal.is_guess)
                self.assertEqual(ui._live_action_count, 0)
                self.assertFalse(ui._simple_auto_pending)
                self.assertEqual(job.validations, [])
                permit = None
                stale_ack = make_ack(proposal, 'LOST') if policy == POLICY_V1 else None
                if policy != POLICY_V1:
                    ui.allow_guess_checkbox.setChecked(True)
                    advance_auto_timer(ui)
                    permit = job.owner.validate(job.validation)
                    stale_ack = k.make_ack(permit, 'LOST')
                self.assertTrue(ui._enter_replay_mode(ReplayPlayer(old.replay)))
                self.assertFalse(ui._replay_mode)  # No Replay before original owner cleanup.
                self.assertIsNotNone(ui._replay_entry_pending)
                self.assertFalse(ui._exit_replay_mode())
                job.complete_cancel()
                self.app.processEvents()
                self.assertTrue(ui._replay_mode)
                self.assertTrue(ui.on_same_board_retry())
                job.proposal_ready.emit(proposal)
                if permit is not None:
                    job.admitted.emit(permit)
                job.acknowledged.emit(stale_ack)
                self.assertEqual(ui._live_action_count, 0)
                self.assertIsNone(ui._v1_pending)
                self.assertIsNone(ui._k_deferred_permit)
                self.assertIsNone(ui._certainty_frame)
                self.assertEqual(ui._k_base_m, ())
                self.assertEqual(ui.live_failure_records, [])

    def test_t6_simple_return_guess_wait_and_first_mine_or_safe_open(self):
        for mine in (0, 2):
            with self.subTest(mine=mine):
                ui = self.make_ui(layout=FixedLayout(5, 1, 1, {(mine, 0)}))
                self.finish(ui)
                ui.on_view_current_replay()
                ui.on_same_board_retry()
                ui.simple_auto_checkbox.setChecked(True)
                self.assertFalse(ui._analysis_first_click)
                self.assertEqual(ui._live_action_count, 0)
                self.assertFalse(ui._simple_auto_pending)
                ui.allow_guess_checkbox.setChecked(True)
                advance_auto_timer(ui)
                ui.simple_auto_checkbox.setChecked(False)
                self.assertEqual(ui._live_action_count, 1)
                self.assertEqual(ui.engine.status, GameStatus.LOST if mine == 0 else GameStatus.PLAYING)
                self.assertEqual(ui._replay_recorder.source_type, SOURCE_ALGORITHM)
                self.assert_empty_group(ui)

    def test_t6_unconfirmed_completion_closing_and_failure_do_not_archive_or_return(self):
        ui = self.make_ui()
        old = self.activate(ui)
        self.finish(ui)
        for field, bad in (('_v1_expected_ack', object()), ('_k_ack_receipt', object()),
                           ('_k_retiring', object()), ('_live_input_uncertain', True),
                           ('_live_first_failure', {'cause': 'failure'}), ('_live_closing', True),
                           ('_live_close_error', 'cleanup failure')):
            with self.subTest(field=field):
                original = getattr(ui, field)
                setattr(ui, field, bad)
                self.assertFalse(ui._capture_completed_for_history())
                self.assertFalse(ui._enter_replay_mode(ReplayPlayer(old.replay)))
                self.assertEqual(ui._same_board_completed_games, [old])
                setattr(ui, field, original)
        ui.on_view_current_replay()
        identity = ui._live_game_id
        for state in ('computing', 'cancelling', 'blocked', 'closed'):
            ui._v1_job.state = state
            self.assertFalse(ui._exit_replay_mode())
            self.assertTrue(ui._replay_mode)
            self.assertEqual(ui._live_game_id, identity)
        ui._v1_job.state = 'idle'
        self.assertTrue(ui._exit_replay_mode())

    def test_t7_exact_cps_model_rate_preferences_and_display_invalidation(self):
        from fractions import Fraction
        from live_pacing import FIXED, MODEL_C
        ui = self.make_ui(POLICY_V1, FixedLayout(9, 9, 10, {(n % 9, n // 9) for n in range(10)}))
        old = self.activate(ui)
        ui.pacing_cps_edit.setText('6')
        ui.pacing_cps_edit.setModified(True)
        ui._commit_pacing_edit(True)
        fixed = ui._fixed_period
        self.assertEqual(fixed.period_ns, 166666667)
        ui.pacing_mode_combo.setCurrentIndex(ui.pacing_mode_combo.findData(MODEL_C))
        ui.pacing_rate_edit.setText('0.5')
        ui.pacing_rate_edit.setModified(True)
        ui._commit_pacing_edit(False)
        rate = ui._pacing_rate
        self.assertEqual(rate.rate, Fraction(1, 2))
        self.assertEqual(ui._pacing_mode, MODEL_C)
        ui.probability_checkbox.setChecked(False)
        ui.reduction_checkbox.setChecked(True)
        ui.auto_cursor_checkbox.setChecked(False)
        ui.auto_cursor_overlay.reserve('old', (2, 0), (4, 0), 1000)
        ui._view_completed_live_game(old)
        previous, generation = ui._live_game_id, ui._live_board_generation
        ui._exit_replay_mode()
        self.assert_fresh_canonical(ui, (9, 9, 10), previous, generation)
        self.assertIs(ui._fixed_period, fixed)
        self.assertIs(ui._pacing_rate, rate)
        self.assertEqual(ui._pacing_mode, MODEL_C)
        ui.pacing_mode_combo.setCurrentIndex(ui.pacing_mode_combo.findData(FIXED))
        self.assertEqual(ui.pacing_cps_edit.text(), '6')
        self.assertFalse(ui.probability_checkbox.isChecked())
        self.assertTrue(ui.reduction_checkbox.isChecked())
        self.assertFalse(ui.auto_cursor_checkbox.isChecked())
        self.assertTrue(all(b.analysis_overlay is None and b.probability_text == '' for b in ui._buttons.values()))

    def test_t7_history_no_focus_popup_and_live_replay_shortcuts(self):
        for key in (Qt.Key_Space, Qt.Key_Return):
            with self.subTest(key=key):
                ui = self.make_ui()
                self.activate(ui)
                ui.show()
                ui.activateWindow()
                ui.setFocus(Qt.OtherFocusReason)
                self.app.processEvents()
                self.assertEqual(ui.same_board_history_button.focusPolicy(), Qt.NoFocus)
                previous = ui._live_game_id
                QTest.keyClick(ui.windowHandle(), key)
                self.assertNotEqual(ui._live_game_id, previous)
                self.assert_empty_group(ui)
        ui = self.make_ui()
        self.activate(ui)
        self.finish(ui)
        ui.show()
        ui.activateWindow()
        ui.setFocus(Qt.OtherFocusReason)
        self.app.processEvents()
        menu = ui.same_board_history_menu
        menu.popup(ui.same_board_history_button.mapToGlobal(QPoint(0, 0)))
        self.app.processEvents()
        self.assertEqual(len(menu.actions()), 2)
        self.assertFalse(ui._game_shortcut_available())
        previous = ui._live_game_id
        QTest.keyClick(menu, Qt.Key_Escape)
        self.app.processEvents()
        self.assertEqual(ui._live_game_id, previous)
        menu.popup(ui.same_board_history_button.mapToGlobal(QPoint(0, 0)))
        menu.setActiveAction(menu.actions()[0])
        QTest.keyClick(menu, Qt.Key_Return)
        self.app.processEvents()
        self.assertTrue(ui._replay_mode)
        self.assertEqual(ui._live_game_id, previous)
        ui.setFocus(Qt.OtherFocusReason)
        QTest.keyClick(ui.windowHandle(), Qt.Key_Space)
        self.assertTrue(ui._replay_autoplay_timer.isActive())
        QTest.keyClick(ui.windowHandle(), Qt.Key_Space)
        self.assertFalse(ui._replay_autoplay_timer.isActive())
        QTest.keyClick(ui.windowHandle(), Qt.Key_Return)
        self.assertTrue(ui._replay_mode)
        self.assertEqual(ui._live_game_id, previous)


if __name__ == '__main__':
    unittest.main()
