"""Two explicit Replay exits; real Qt/engine with registered fake worker seams."""
from fractions import Fraction
import random
from unittest.mock import patch

from PyQt5 import sip
from PyQt5.QtCore import QPoint, QRect, Qt
from PyQt5.QtTest import QTest

from core_engine import GameStatus
import live_k_policy as k
from live_policy import CANONICAL_NEW, FIXED_BOARD, POLICY_SIMPLE, POLICY_V1, plan_snapshot
from live_pacing import FIXED, MODEL_C
from live_same_board import FixedLayout
from replay_model import ReplayBoard, ReplayData, ReplayEvent, SOURCE_ALGORITHM, SOURCE_HUMAN
from replay_player import ReplayPlayer
from tests.test_live_auto import advance_auto_timer
from tests.test_live_replay_entry_ui import ReplayEntryUI


class ReplayExitUI(ReplayEntryUI):
    # Only this class's explicit new IDs are selected, never inherited discovery.
    def test_explicit_same_board_all_routes_and_positions_preserve_detached_group(self):
        for route in ('current', 'history', 'file'):
            for index in (0, 1, 2):
                with self.subTest(route=route, index=index):
                    layout = FixedLayout(5, 1, 1, {(2, 0)})
                    ui = self.make_ui(layout=layout)
                    if route == 'history':
                        self.activate(ui)
                    ui.on_left_click(0, 0)
                    self.finish(ui)
                    data = ui._build_current_replay_data('exit fixture', require_finished=True)
                    if route == 'current':
                        ui.on_view_current_replay()
                    elif route == 'history':
                        ui._view_completed_live_game(ui._same_board_completed_games[0])
                        ui._view_completed_live_game(ui._same_board_completed_games[-1])
                    else:
                        ui._rebuild_game(9, 9, 10)  # Foreign Live dimensions must not leak into return.
                        self.load(ui, self.save_fixture(data))
                    group = tuple(ui._same_board_completed_games)
                    evidence = tuple((item.game_id, item.layout, item.replay, item.evidence_json) for item in group)
                    ui._replay_player.go_to(index)
                    ui._refresh_replay_view_after_move()
                    if index == 1:
                        ui.on_replay_play_pause()
                    prior, generation = ui._live_game_id, ui._live_board_generation
                    with patch.object(ui, '_ask_custom_dimensions', side_effect=AssertionError('No modal')):
                        ui.same_board_retry_button.click()
                    self.assert_fresh_fixed(ui, layout, prior, generation)
                    self.assertEqual(tuple(ui._same_board_completed_games), group)
                    self.assertEqual(tuple((g.game_id, g.layout, g.replay, g.evidence_json) for g in group), evidence)
                    self.assertFalse(ui._replay_autoplay_timer.isActive())
                    if not group:
                        self.assert_empty_group(ui)

    def test_default_button_and_api_clear_group_without_installing_layout_or_rng_draw(self):
        for route in ('api', 'button_false', 'button_true'):
            with self.subTest(route=route):
                ui = self.make_ui()
                old = self.activate(ui)
                action = ui.same_board_history_menu.actions()[0]
                self.finish(ui)
                ui._view_completed_live_game(old)
                self.assertEqual(len(ui._same_board_completed_games), 2)
                prior, generation = ui._live_game_id, ui._live_board_generation
                state = random.getstate()
                with patch.object(ui.engine, 'reset_with_mines', side_effect=AssertionError('Default must not install mines')), \
                     patch.object(FixedLayout, 'from_replay_board', side_effect=AssertionError('Default must use dimensions only')):
                    if route == 'api':
                        self.assertTrue(ui._exit_replay_mode())
                    else:
                        ui.exit_replay_button.clicked.emit(route == 'button_true')
                self.assertEqual(random.getstate(), state)
                self.assert_fresh_canonical(ui, (9, 9, 10), prior, generation)
                ui._view_completed_live_game(old)
                if not sip.isdeleted(action):
                    action.trigger()
                self.assertFalse(ui._replay_mode)
                old.layout.reset_engine(ui.engine)  # Accidental matching next board cannot revive a cleared group.
                ui.same_board_history_menu.aboutToShow.emit()
                self.assert_empty_group(ui)

    def test_repeat_same_board_preserves_attempts_then_default_or_live_reset_clears(self):
        for final in ('default', 'live_reset'):
            with self.subTest(final=final):
                ui = self.make_ui()
                old = self.activate(ui)
                ids = [old.game_id]
                for _ in range(2):
                    ui._replay_recorder.source_type = SOURCE_ALGORITHM
                    self.finish(ui)
                    ids.append(ui._live_game_id)
                    ui._view_completed_live_game(old)
                    group = tuple(ui._same_board_completed_games)
                    frozen = tuple((g.game_id, g.replay, g.evidence_json) for g in group)
                    for _ in range(2):
                        ui._view_completed_live_game(old)
                    self.assertTrue(ui.on_same_board_retry())
                    self.assertEqual([g.game_id for g in ui._same_board_completed_games], ids)
                    self.assertEqual(tuple((g.game_id, g.replay, g.evidence_json) for g in group), frozen)
                    self.assertEqual([g.replay.source_type for g in group], [SOURCE_HUMAN]+[SOURCE_ALGORITHM]*(len(ids)-1))
                ui._view_completed_live_game(old)
                if final == 'default':
                    ui.on_exit_replay()
                else:
                    ui.on_same_board_retry()
                    ui.on_reset()
                self.assert_empty_group(ui)
                self.assertIsNone(ui._live_fixed_origin)
                self.assertFalse(ui.engine.get_board_snapshot().mines_placed)
                ui._view_completed_live_game(old)
                self.assertFalse(ui._replay_mode)

    def test_empty_imported_incomplete_and_foreign_presets_custom_both_exits(self):
        for dims in ((9, 9, 10), (16, 16, 40), (30, 16, 99), (6, 2, 2)):
            for same in (False, True):
                for incomplete in (False, True):
                    with self.subTest(dims=dims, same=same, incomplete=incomplete):
                        ui = self.make_ui(POLICY_V1)
                        mines = {(n % dims[0], n // dims[0]) for n in range(dims[2])}
                        layout = FixedLayout(*dims, mines)
                        data = ReplayData(ReplayBoard(*dims, mines), (ReplayEvent(.1, 0, 0, 'FLAG'),) if incomplete else ())
                        path = self.save_fixture(data)
                        saved = path.read_bytes()
                        self.load(ui, path)
                        ui._replay_player.go_to(len(data.events))
                        prior, generation = ui._live_game_id, ui._live_board_generation
                        with patch.object(ui, '_ask_custom_dimensions', side_effect=AssertionError('No modal')):
                            self.assertTrue(ui._exit_replay_mode(same_board=same))
                        if same:
                            self.assert_fresh_fixed(ui, layout, prior, generation)
                        else:
                            self.assert_fresh_canonical(ui, dims, prior, generation)
                        self.assert_empty_group(ui)
                        self.assertEqual(path.read_bytes(), saved)  # External Replay JSON is never deleted/rewritten.
                        self.assertEqual(ui._v1_supported(), dims != (6, 2, 2))
                        self.assertEqual(ui.simple_auto_checkbox.isEnabled(), dims != (6, 2, 2))
                        if dims == (6, 2, 2):
                            ui.live_policy_combo.setCurrentIndex(ui.live_policy_combo.findData(POLICY_SIMPLE))
                            self.assertTrue(ui.simple_auto_checkbox.isEnabled())

    def test_two_exit_guards_preserve_replay_position_autoplay_group_and_engine(self):
        ui = self.make_ui()
        old = self.activate(ui)
        ui._view_completed_live_game(old)
        ui.on_replay_play_pause()
        player = ui._replay_player
        before = (ui._live_game_id, ui._live_board_generation, ui.engine.get_board_snapshot(),
                  tuple(ui._same_board_completed_games), tuple(ui.same_board_history_menu.actions()),
                  ui._normal_game_config, player.current_index, ui._replay_autoplay_timer.isActive())
        guards = [('_live_closing', True), ('_live_close_error', 'original cleanup'),
                  ('_live_input_uncertain', True), ('_live_first_failure', {'cause': 'original ACK'}),
                  ('_v1_owned', True), ('_v1_expected_ack', object()), ('_k_retiring', object())]
        for field, value in guards:
            for same in (False, True):
                with self.subTest(field=field, same=same), patch.object(ui, field, value):
                    ui._update_policy_controls()
                    self.assertFalse(ui.exit_replay_button.isEnabled())
                    self.assertFalse(ui.same_board_retry_button.isEnabled())
                    self.assertFalse(ui._exit_replay_mode(same_board=same))
                    self.assertIs(ui._replay_player, player)
                    self.assertEqual((ui._live_game_id, ui._live_board_generation, ui.engine.get_board_snapshot(),
                        tuple(ui._same_board_completed_games), tuple(ui.same_board_history_menu.actions()),
                        ui._normal_game_config, player.current_index, ui._replay_autoplay_timer.isActive()), before)
        for state in ('computing', 'cancelling', 'blocked', 'closed'):
            with self.subTest(state=state), patch.object(ui._v1_job, 'state', state):
                self.assertFalse(ui.on_exit_replay())
                self.assertFalse(ui.on_same_board_retry())
                self.assertIs(ui._replay_player, player)
                self.assertEqual(tuple(ui._same_board_completed_games), before[3])
        with self.assertRaises(TypeError):
            ui._exit_replay_mode(True)  # clicked(bool) cannot become the choice argument.
        self.assertIs(ui._replay_player, player)

    def test_exact_settings_display_preferences_keyboard_and_separate_narrow_rows(self):
        for same in (False, True):
            with self.subTest(same=same):
                ui = self.make_ui(POLICY_V1)
                old = self.activate(ui)
                ui.pacing_cps_edit.setText('6')
                ui.pacing_cps_edit.setModified(True)
                ui._commit_pacing_edit(True)
                ui.pacing_mode_combo.setCurrentIndex(ui.pacing_mode_combo.findData(MODEL_C))
                ui.pacing_rate_edit.setText('0.5')
                ui.pacing_rate_edit.setModified(True)
                ui._commit_pacing_edit(False)
                ui.probability_checkbox.setChecked(False)
                ui.reduction_checkbox.setChecked(True)
                ui.auto_cursor_checkbox.setChecked(False)
                ui._view_completed_live_game(old)
                ui.show()
                ui.resize(480, 620)
                ui.activateWindow()
                ui.setFocus(Qt.OtherFocusReason)
                self.pump()
                self.assertEqual(ui.same_board_retry_button.focusPolicy(), Qt.NoFocus)
                self.assertEqual(ui.exit_replay_button.focusPolicy(), Qt.NoFocus)
                self.assertTrue(ui.same_board_retry_button.isVisible())
                self.assertTrue(ui.exit_replay_button.isVisible())
                retry_rect = QRect(ui.same_board_retry_button.mapTo(ui, QPoint()), ui.same_board_retry_button.size())
                exit_rect = QRect(ui.exit_replay_button.mapTo(ui, QPoint()), ui.exit_replay_button.size())
                self.assertFalse(retry_rect.intersects(exit_rect))
                self.assertIn('기록은 유지', ui.same_board_retry_button.toolTip())
                self.assertIn('비워집니다', ui.exit_replay_button.toolTip())
                for key in (Qt.Key_Return, Qt.Key_Enter):
                    QTest.keyClick(ui.windowHandle(), key)
                    self.assertTrue(ui._replay_mode)
                QTest.keyClick(ui.windowHandle(), Qt.Key_Space)
                self.assertTrue(ui._replay_autoplay_timer.isActive())
                QTest.keyClick(ui.windowHandle(), Qt.Key_Space)
                self.assertFalse(ui._replay_autoplay_timer.isActive())
                prior, generation = ui._live_game_id, ui._live_board_generation
                (ui.same_board_retry_button if same else ui.exit_replay_button).click()
                if same:
                    self.assert_fresh_fixed(ui, old.layout, prior, generation)
                else:
                    self.assert_fresh_canonical(ui, (9, 9, 10), prior, generation)
                self.assertEqual(ui._fixed_period.target_cps, Fraction(6))
                self.assertEqual(ui._fixed_period.period_ns, 166666667)
                self.assertEqual(ui._pacing_rate.rate, Fraction(1, 2))
                self.assertEqual(ui._pacing_mode, MODEL_C)
                self.assertFalse(ui.probability_checkbox.isChecked())
                self.assertTrue(ui.reduction_checkbox.isChecked())
                self.assertFalse(ui.auto_cursor_checkbox.isChecked())
                self.assertTrue(all(b.analysis_overlay is None and b.probability_text == '' for b in ui._buttons.values()))
                previous = ui._live_game_id
                QTest.keyClick(ui.windowHandle(), Qt.Key_Return)
                self.assertNotEqual(ui._live_game_id, previous)
                self.assert_empty_group(ui)

    def test_all_policies_first_auto_canonical_safe_and_fixed_guess_loss(self):
        layout = FixedLayout(9, 9, 10, {(0, 0)} | {(x, 8) for x in range(9)})
        for policy in (POLICY_SIMPLE, POLICY_V1, k.POLICY_K, k.POLICY_K_LC0, k.POLICY_K_LC1):
            for same in (False, True):
                with self.subTest(policy=policy, same=same):
                    ui = self.make_ui(policy, layout)
                    old = self.activate(ui)
                    ui._view_completed_live_game(old)
                    self.assertTrue(ui._exit_replay_mode(same_board=same))
                    job = ui._v1_job
                    ui.live_action_applied.connect(lambda row, target=ui: target.simple_auto_checkbox.setChecked(False))
                    ui.simple_auto_checkbox.setChecked(True)
                    if policy != POLICY_SIMPLE:
                        if policy == POLICY_V1:
                            job.deliver(plan_snapshot(job.requests[-1]))
                        else:
                            job.compute()
                        self.assertEqual(job.pending.snapshot.entry_mode, FIXED_BOARD if same else CANONICAL_NEW)
                        self.assertEqual(job.pending.snapshot.input_revision, 0)
                        self.assertEqual(job.pending.is_guess, same)
                        self.assertEqual(job.pending.initial, not same)
                    if same:
                        self.assertEqual(ui._live_action_count, 0)
                        self.assertFalse(ui._simple_auto_pending)
                        ui.allow_guess_checkbox.setChecked(True)
                    advance_auto_timer(ui)
                    if policy not in (POLICY_SIMPLE, POLICY_V1):
                        job.deliver_admission()
                    ui.simple_auto_checkbox.setChecked(False)
                    self.assertEqual(ui._live_action_count, 1)
                    self.assertEqual(len(ui._replay_recorder.events), 1)
                    self.assertEqual(ui._replay_recorder.source_type, SOURCE_ALGORITHM)
                    if same:
                        self.assertEqual(ui.engine.status, GameStatus.LOST)
                        self.assertTrue(layout.matches(ui.engine.get_board_snapshot()))
                    else:
                        self.assertNotEqual(ui.engine.status, GameStatus.LOST)
                        self.assertNotIn((0, 0), ui.engine.get_board_snapshot().mines)
                        self.assertIsNone(ui._live_fixed_origin)
                    if policy != POLICY_SIMPLE:
                        if ui.engine.status == GameStatus.PLAYING:
                            job.deliver_ack()
                            ui._invalidate_v1_run('fixture normal retirement', drain_ack=True)
                            job.complete_cancel()
                        else:
                            job.finish_record(terminal=True)
                        self.pump()
                        self.assertEqual(len(job.acks), 1)
                        self.assertEqual(ui.live_failure_records, [])

