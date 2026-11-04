"""Replay presentation and real Qt keyboard routing, without policy workers."""
from copy import deepcopy
from dataclasses import replace
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtTest import QSignalSpy, QTest
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QDialog, QLineEdit, QPlainTextEdit,
    QPushButton, QShortcut, QStyle, QStyleOptionComboBox, QTextEdit, QVBoxLayout,
)

from live_policy import POLICY_K, POLICY_SIMPLE, POLICY_V1
from replay_json import load_replay_json, replay_data_from_dict, replay_data_to_dict
from replay_model import SOURCE_AI, SOURCE_ALGORITHM, SOURCE_HUMAN
from replay_player import ReplayPlayer
from tests.test_replay_analysis_ui import ReplayAnalysisUITests, replay_data
from ui_manager import REPLAY_MODE_INDEX, REPLAY_MODE_TIME


class ReplayUIPolishTests(unittest.TestCase):
    setUpClass = ReplayAnalysisUITests.__dict__['setUpClass']
    close_ui = ReplayAnalysisUITests.close_ui

    def setUp(self):
        ReplayAnalysisUITests.setUp(self)
        self.ui.show()
        self.focus_board()

    def focus_board(self):
        self.ui.activateWindow()
        self.ui.setFocus(Qt.OtherFocusReason)
        self.app.processEvents()

    def enter(self, data=None, index=0):
        self.player = ReplayPlayer(data or replay_data())
        self.player.go_to(index)
        self.ui._enter_replay_mode(self.player)
        self.focus_board()

    def key(self, key):
        # QWindow dispatch exercises shortcut resolution, not a direct slot.
        QTest.keyClick(self.ui.windowHandle(), key)

    def live_state(self):
        ui = self.ui
        return deepcopy((
            ui.engine.get_observation(), ui.engine.get_counter_snapshot(),
            ui._live_game_id, ui._live_board_generation, ui._live_action_count,
            ui._v1_timer_nonce, ui._k_validation_nonce, ui._v1_cursor,
            ui._v1_job.state, ui._v1_job.active_run_id,
            ui._replay_recorder.board, ui._replay_recorder.events,
            ui._replay_recorder.source_type, ui.live_input_records,
            ui.live_action_records, ui.live_owner_records, ui.live_auto_totals,
        ))

    def replay_state(self):
        ui = self.ui
        return (self.live_state(), ui._replay_data, self.player.current_index,
                self.player.engine.get_observation(), ui._replay_view_index,
                ui._replay_time_anchor_wall, ui._replay_time_anchor_replay,
                ui._replay_display_time_override, ui._replay_autoplay_timer.isActive(),
                ui.live_policy_status_label.text(), ui.analysis_status_label.text(),
                ui._analysis_result, ui._replay_analysis_result,
                tuple((button.analysis_overlay, button.probability_text)
                      for button in ui._buttons.values()))

    def test_policy_row_stays_adjacent_at_two_widths_and_expert_scrolls(self):
        self.ui._rebuild_game(30, 16, 99)
        controls = (self.ui.live_policy_label, self.ui.live_policy_combo,
                    self.ui.live_policy_new_game_button)
        frames = []
        for width in (1080, 1580):
            with self.subTest(width=width):
                self.ui.resize(width, 760)
                self.app.processEvents()
                rects = [control.geometry() for control in controls]
                gaps = [rects[i+1].left() - rects[i].right() - 1 for i in range(2)]
                for gap in gaps:
                    self.assertGreaterEqual(gap, 0)
                    self.assertLessEqual(gap, controls[0].fontMetrics().height())
                self.assertGreater(controls[0].fontMetrics().horizontalAdvance(controls[0].text()), 0)
                for control in (controls[0], controls[2]):
                    self.assertGreaterEqual(control.width(), control.sizeHint().width())
                option = QStyleOptionComboBox()
                option.initFrom(controls[1])
                edit_rect = controls[1].style().subControlRect(
                    QStyle.CC_ComboBox, option, QStyle.SC_ComboBoxEditField, controls[1])
                for index in range(controls[1].count()):
                    self.assertGreaterEqual(edit_rect.width(), controls[1].fontMetrics().horizontalAdvance(
                        controls[1].itemText(index)))
                self.assertTrue(controls[1].model().item(controls[1].findData('K_LC0')).isEnabled())
                self.assertTrue(controls[1].model().item(controls[1].findData('K_LC1')).isEnabled())
                frames.append((self.ui.width(), tuple((r.x(), r.width()) for r in rects)))
                evidence = os.environ.get('REPLAY_POLISH_EVIDENCE')
                if evidence:
                    self.assertTrue(self.ui.grab().save(str(Path(evidence) / f'layout_{width}.png')))
        self.assertEqual(frames[0][1], frames[1][1])
        self.assertGreater(frames[1][0], frames[0][0])
        self.ui.cell_size_spin.setValue(50)
        self.ui.resize(1080, 600)
        self.app.processEvents()
        self.assertGreater(self.ui.scroll_area.horizontalScrollBar().maximum(), 0)
        self.assertGreater(self.ui.scroll_area.verticalScrollBar().maximum(), 0)

    def test_source_record_is_independent_of_policy_and_reference_analysis(self):
        for source in (SOURCE_HUMAN, SOURCE_ALGORITHM, SOURCE_AI):
            with self.subTest(source=source):
                self.enter(replace(replay_data(), source_type=source), index=1)
                expected = '알고리즘 사용 기록: ' + ('없음' if source == SOURCE_HUMAN else '있음')
                before = deepcopy((self.engine.get_observation(), self.engine.get_counter_snapshot(),
                                   self.ui._replay_recorder.events))
                for policy in (POLICY_K, POLICY_V1, POLICY_SIMPLE):
                    self.ui.live_policy_combo.blockSignals(True)
                    self.ui.live_policy_combo.setCurrentIndex(self.ui.live_policy_combo.findData(policy))
                    self.ui.live_policy_combo.blockSignals(False)
                    self.ui.analysis_checkbox.setChecked(True)
                    self.ui.analyze_button.click()
                    self.ui.probability_checkbox.toggle()
                    self.ui.auto_cursor_checkbox.toggle()
                    self.ui._update_policy_controls()
                    self.assertEqual(self.ui.live_policy_status_label.text(), expected)
                    self.assertEqual(self.ui._replay_data.source_type, source)
                    self.assertEqual((self.engine.get_observation(), self.engine.get_counter_snapshot(),
                                      self.ui._replay_recorder.events), before)
                for control in (self.ui.live_policy_label, self.ui.live_policy_combo,
                                self.ui.live_policy_new_game_button, self.ui.simple_auto_checkbox):
                    self.assertTrue(control.isHidden())
                self.assertIn('참고', self.ui.analyze_button.text())
                self.assertNotIn('Stage', self.ui.live_policy_status_label.text())
                evidence = os.environ.get('REPLAY_POLISH_EVIDENCE')
                if evidence:
                    self.app.processEvents()
                    self.assertTrue(self.ui.grab().save(str(Path(evidence) / f'replay_{source}.png')))

    def test_load_save_and_save_as_keep_type_events_and_missing_source_default(self):
        directory = Path(self.settings.fileName()).parent
        self.settings.setValue('replay/default_directory', str(directory))
        for source in (SOURCE_HUMAN, SOURCE_ALGORITHM, SOURCE_AI, None):
            with self.subTest(source=source):
                raw = replay_data_to_dict(replace(replay_data(), source_type=source or SOURCE_HUMAN))
                if source is None:
                    del raw['source_type']
                path = directory / f'input_{source}.json'
                path.write_text(json.dumps(raw), encoding='utf-8')
                expected = replay_data_from_dict(raw)
                with patch('ui_manager.QFileDialog.getOpenFileName', return_value=(str(path), 'JSON')):
                    self.ui.on_load_replay()
                self.assertEqual(self.ui._replay_data, expected)
                existing = set(directory.glob('*.json'))
                with patch('ui_manager.QMessageBox.information'):
                    self.ui.on_save_replay()
                saved = set(directory.glob('*.json')) - existing
                self.assertEqual(len(saved), 1)
                self.assertEqual(load_replay_json(saved.pop()), expected)
                alternate = directory / f'copy_{source}.json'
                with patch('ui_manager.QFileDialog.getSaveFileName', return_value=(str(alternate), 'JSON')), \
                        patch('ui_manager.QMessageBox.information'):
                    self.ui.on_save_replay_as()
                self.assertEqual(load_replay_json(alternate), expected)
                self.assertEqual(self.ui._replay_data.events, expected.events)
                self.assertEqual('없음' in self.ui.live_policy_status_label.text(), expected.source_type == SOURCE_HUMAN)
        raw['source_type'] = 'unrecognized'
        with self.assertRaises(ValueError):
            replay_data_from_dict(raw)

    def test_missing_internal_replay_data_never_claims_human_or_algorithm(self):
        self.enter()
        self.ui._replay_data = None
        self.ui._update_policy_controls()
        self.assertEqual(self.ui.live_policy_status_label.text(), '알고리즘 사용 기록: 확인 불가')

    def test_only_actual_auto_input_marks_record_and_manual_policy_changes_keep_it(self):
        self.engine.reset_with_mines(3, 3, 1, {(1, 1)})
        self.ui.on_left_click(0, 0)
        self.ui.on_right_click(2, 2)
        self.ui.simple_auto_checkbox.setChecked(True)
        self.ui.simple_auto_checkbox.setChecked(False)
        self.assertEqual(self.ui._replay_recorder.source_type, SOURCE_HUMAN)
        before = len(self.ui._replay_recorder.events)
        self.ui.simple_auto_checkbox.setChecked(True)
        self.ui._simple_auto_timer.stop()
        self.ui._on_simple_auto_timeout()
        self.assertEqual(len(self.ui._replay_recorder.events), before + 1)
        self.assertEqual(self.ui.live_action_records[-1]['semantic_input'], 'UNFLAG')
        self.assertEqual(self.ui._replay_recorder.source_type, SOURCE_ALGORITHM)
        self.ui.on_right_click(2, 1)
        self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
        self.assertFalse(self.ui.allow_guess_checkbox.isChecked())
        for policy in (POLICY_K, POLICY_V1, POLICY_SIMPLE):
            self.ui.live_policy_combo.setCurrentIndex(self.ui.live_policy_combo.findData(policy))
            self.assertEqual(self.ui._replay_recorder.source_type, SOURCE_ALGORITHM)
        data = self.ui._replay_recorder.to_replay_data()
        self.enter(data)
        self.assertEqual(self.ui._replay_data, data)
        self.assertEqual(self.ui.live_policy_status_label.text(), '알고리즘 사용 기록: 있음')

    def test_space_start_pause_resume_routes_once_in_index_and_time_modes(self):
        for mode in (REPLAY_MODE_INDEX, REPLAY_MODE_TIME):
            with self.subTest(mode=mode), patch('ui_manager.time.perf_counter', return_value=100.0):
                self.enter()
                self.ui.replay_playback_mode_combo.setCurrentText(mode)
                before = self.live_state()
                clicks = QSignalSpy(self.ui.replay_play_button.clicked)
                for count, playing in enumerate((True, False, True, False), 1):
                    self.key(Qt.Key_Space)
                    self.assertEqual(len(clicks), count)
                    self.assertEqual(self.ui._replay_autoplay_timer.isActive(), playing)
                    self.assertEqual(self.player.current_index, 0)
                    self.assertEqual(self.live_state(), before)
                    self.assertNotIn('새 게임', self.ui.analysis_status_label.text())

    def test_space_at_end_or_empty_never_restarts_or_resets(self):
        for empty in (False, True):
            with self.subTest(empty=empty):
                data = replace(replay_data(), events=()) if empty else replay_data()
                self.enter(data, index=len(data.events))
                before = self.replay_state()
                clicks = QSignalSpy(self.ui.replay_play_button.clicked)
                self.key(Qt.Key_Space)
                self.assertEqual(self.replay_state(), before)
                self.assertEqual(len(clicks), 0)

    def test_replay_direct_reset_return_and_enter_preserve_all_state(self):
        self.enter(index=1)
        self.ui.on_analyze_current()
        before = self.replay_state()
        with patch.object(self.ui, '_invalidate_v1_run') as invalidate, \
                patch.object(self.engine, 'reset') as reset:
            self.ui.on_reset()
            self.key(Qt.Key_Return)
            self.key(Qt.Key_Enter)
            self.ui.live_policy_combo.blockSignals(True)
            self.ui.live_policy_combo.setCurrentIndex(self.ui.live_policy_combo.findData('K_LC0'))
            self.ui.on_reset()
            self.ui.live_policy_combo.blockSignals(False)
        invalidate.assert_not_called()
        reset.assert_not_called()
        self.assertEqual(self.replay_state(), before)

    def test_live_space_return_enter_each_reset_once_and_clear_recording(self):
        for key in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            with self.subTest(key=key):
                self.ui.on_right_click(2, 2)
                self.focus_board()
                with patch.object(self.engine, 'reset', wraps=self.engine.reset) as reset:
                    self.key(key)
                reset.assert_called_once_with()
                self.assertEqual(self.ui._replay_recorder.events, ())
                self.assertEqual(self.ui._live_action_count, 0)
                self.assertEqual(self.ui._v1_job.state, 'idle')

    def test_mouse_selected_policy_keeps_combo_focus_and_each_key_resets_once(self):
        combo = self.ui.live_policy_combo
        self.assertFalse(combo.isEditable())
        self.assertNotEqual(combo.focusPolicy(), Qt.NoFocus)
        for key, policy in ((Qt.Key_Space, POLICY_V1), (Qt.Key_Return, POLICY_K),
                            (Qt.Key_Enter, POLICY_SIMPLE)):
            with self.subTest(key=key, policy=policy):
                # Follow the mouse selection path; never move focus away before the key.
                QTest.mouseClick(combo, Qt.LeftButton)
                self.app.processEvents()
                self.assertIsNotNone(QApplication.activePopupWidget())
                view = combo.view()
                index = combo.model().index(combo.findData(policy), combo.modelColumn())
                rect = view.visualRect(index)
                self.assertTrue(rect.isValid())
                # Let Qt's popup release guard expire, then move and click as a user does.
                QTest.qWait(QApplication.doubleClickInterval() + 20)
                QTest.mouseMove(view.viewport(), rect.center())
                QTest.mouseClick(view.viewport(), Qt.LeftButton, pos=rect.center())
                self.app.processEvents()
                self.assertIsNone(QApplication.activePopupWidget())
                self.assertIs(QApplication.focusWidget(), combo)
                self.assertEqual(combo.currentData(), policy)
                with patch.object(self.engine, 'reset', wraps=self.engine.reset) as reset, \
                        patch.object(self.engine, 'step') as step, \
                        patch.object(self.ui._v1_job, 'start') as start:
                    self.key(key)
                reset.assert_called_once_with()
                step.assert_not_called()
                start.assert_not_called()
                self.assertIsNone(QApplication.activePopupWidget())
                self.assertIs(QApplication.focusWidget(), combo)
                self.assertEqual(combo.currentData(), policy)
                self.assertEqual(self.ui._live_policy, policy)
                self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
                self.assertFalse(self.ui.allow_guess_checkbox.isChecked())
                self.assertFalse(self.ui.allow_guess_checkbox.isEnabled())
                self.assertEqual(self.ui._replay_recorder.events, ())
                self.assertEqual(self.ui._live_action_count, 0)
                self.assertEqual(self.ui._v1_job.state, 'idle')
                self.assertIsNone(self.ui._v1_job.active_run_id)

    def assert_close_failure_is_visible_and_inert(self):
        ui = self.ui
        cause = 'cleanup retained: <owned directory>\n' + '긴 내부 오류; ' * 300
        job = SimpleNamespace(state='blocked', active_run_id='retained-fake-owner',
                              last_record=None, cancel=Mock(), start=Mock(), request=Mock(),
                              shutdown=Mock(side_effect=RuntimeError(cause)))
        height = ui.live_policy_status_label.height()
        latch = deepcopy((ui._live_first_failure, ui._live_input_uncertain, ui._v1_manual_only))
        with patch.object(ui, '_v1_job', job), \
                patch.object(ui, '_create_v1_job') as create_job, \
                patch.object(self.engine, 'reset') as reset, \
                patch.object(self.engine, 'step') as step:
            self.assertFalse(ui.close())
            self.assertTrue(ui.isVisible())
            self.assertTrue(ui._live_closing)
            self.assertIs(ui._v1_job, job)
            job.shutdown.assert_called_once_with()
            job.cancel.assert_called_once_with('창 닫기')
            self.assertEqual((job.state, job.active_run_id), ('blocked', 'retained-fake-owner'))
            self.assertEqual((ui._live_first_failure, ui._live_input_uncertain, ui._v1_manual_only), latch)
            before = self.live_state()
            for refresh in (ui._update_policy_controls, ui._update_replay_controls):
                refresh()
                self.assertIn('종료 정리에 실패했습니다', ui.live_policy_status_label.display_text())
                self.assertIn(cause, ui.live_policy_status_label.toolTip())
                self.assertIn(cause, ui.live_policy_status_label.accessibleDescription())
                self.assertEqual(ui.live_policy_status_label.height(), height)
                for control in (ui.reset_button, ui.live_policy_new_game_button,
                                ui.live_policy_combo, ui.difficulty_combo, ui.simple_auto_checkbox,
                                ui.simple_auto_interval_spin, ui.allow_guess_checkbox):
                    self.assertFalse(control.isEnabled())
            for key in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
                self.key(key)
            ui.on_reset()
            ui.reset_button.click()
            ui.live_policy_new_game_button.click()
            ui.on_left_click(0, 0)
            self.assertEqual(self.live_state(), before)
            # A canceled delivery revokes its reservation once, without any input.
            ui._on_simple_auto_timeout()
            expected = before[:5] + (before[5] + 1,) + before[6:]
            self.assertEqual(self.live_state(), expected)
            reset.assert_not_called()
            step.assert_not_called()
            create_job.assert_not_called()
            job.start.assert_not_called()
            job.request.assert_not_called()
            self.assertFalse(ui._simple_auto_timer.isActive())
            save = ui.replay_mode_save_as_button if ui._replay_mode else ui.save_replay_as_button
            self.assertTrue(save.isEnabled())
            evidence = os.environ.get('REPLAY_POLISH_EVIDENCE')
            if evidence:
                self.app.processEvents()
                mode = 'replay' if ui._replay_mode else 'live'
                self.assertTrue(ui.grab().save(str(Path(evidence) / f'close_failure_{mode}.png')))

    def test_fake_shutdown_failure_keeps_live_window_reason_and_controls_inert(self):
        self.assert_close_failure_is_visible_and_inert()

    def test_fake_shutdown_failure_keeps_replay_reason_and_save_available(self):
        self.enter(index=1)
        self.assert_close_failure_is_visible_and_inert()
        self.assertEqual(self.player.current_index, 1)
        self.assertFalse(self.ui._replay_autoplay_timer.isActive())

    def test_normal_close_has_no_failure_message_and_accepts(self):
        self.assertIsNone(self.ui._live_close_error)
        self.assertNotIn('종료 정리에 실패했습니다', self.ui.live_policy_status_label.text())
        self.assertTrue(self.ui.close())
        self.assertFalse(self.ui.isVisible())
        self.assertEqual(self.ui._v1_job.state, 'closed')
        self.assertIsNone(self.ui._live_close_error)

    def test_auxiliary_close_refusal_restores_live_controls_after_clean_shutdown(self):
        job = self.ui._v1_job
        with patch.object(self.ui, '_stage3_visualizer_launcher', SimpleNamespace(close=lambda: False)):
            self.assertFalse(self.ui.close())
        self.assertTrue(self.ui.isVisible())
        self.assertFalse(self.ui._live_closing)
        self.assertIsNone(self.ui._live_close_error)
        self.assertIsNot(self.ui._v1_job, job)
        self.assertEqual(self.ui._v1_job.state, 'idle')
        self.assertNotIn('종료 정리에 실패했습니다', self.ui.live_policy_status_label.text())
        for control in (self.ui.reset_button, self.ui.live_policy_new_game_button,
                        self.ui.live_policy_combo, self.ui.difficulty_combo,
                        self.ui.simple_auto_checkbox, self.ui.simple_auto_interval_spin):
            self.assertTrue(control.isEnabled())
        with patch.object(self.engine, 'reset', wraps=self.engine.reset) as reset:
            self.ui.reset_button.click()
        reset.assert_called_once_with()

    def test_editing_widgets_keep_space_and_return_without_game_shortcuts(self):
        for replay in (False, True):
            if replay:
                self.enter()
            for widget_type in (QLineEdit, QTextEdit, QPlainTextEdit):
                with self.subTest(replay=replay, editor=widget_type.__name__):
                    editor = widget_type(self.ui)
                    editor.show()
                    editor.setFocus()
                    self.app.processEvents()
                    before = self.live_state()
                    QTest.keyClicks(editor, 'a b')
                    QTest.keyClick(editor, Qt.Key_Return)
                    self.assertEqual(self.live_state(), before)
                    value = editor.text() if isinstance(editor, QLineEdit) else editor.toPlainText()
                    self.assertIn('a b', value)
                    self.assertFalse(self.ui._replay_autoplay_timer.isActive())
                    editor.close()
                    editor.deleteLater()
            spin = self.ui.replay_index_interval_spin if replay else self.ui.simple_auto_interval_spin
            spin.setFocus()
            self.app.processEvents()
            before = self.live_state()
            for key in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
                QTest.keyClick(spin, key)
            self.assertEqual(self.live_state(), before)
            self.assertFalse(self.ui._replay_autoplay_timer.isActive())
            combo = QComboBox(self.ui)
            combo.setEditable(True)
            combo.addItem('a')
            combo.show()
            combo.lineEdit().setFocus()
            combo.lineEdit().setCursorPosition(1)
            self.app.processEvents()
            before = self.live_state()
            QTest.keyClicks(combo.lineEdit(), ' b')
            self.assertEqual(combo.currentText(), 'a b')
            self.assertEqual(self.live_state(), before)
            combo.close()
            combo.deleteLater()
            self.focus_board()

    def test_combo_popup_and_modal_receive_keys_without_replay_toggle(self):
        self.enter()
        before = self.live_state()
        combo = self.ui.replay_playback_mode_combo
        combo.showPopup()
        self.app.processEvents()
        popup = QApplication.activePopupWidget()
        self.assertIsNotNone(popup)
        QTest.keyClick(popup, Qt.Key_Space)
        self.assertFalse(self.ui._replay_autoplay_timer.isActive())
        combo.hidePopup()
        dialog = QDialog(self.ui)
        dialog.setModal(True)
        layout = QVBoxLayout(dialog)
        edit = QLineEdit(dialog)
        accept = QPushButton('Accept', dialog)
        accept.setDefault(True)
        layout.addWidget(edit)
        layout.addWidget(accept)
        dialog.show()
        edit.setFocus()
        self.app.processEvents()
        self.assertIs(QApplication.activeModalWidget(), dialog)
        clicks = QSignalSpy(accept.clicked)
        QTest.keyClicks(edit, 'a b')
        QTest.keyClick(edit, Qt.Key_Return)
        self.assertEqual(edit.text(), 'a b')
        self.assertEqual(len(clicks), 1)
        self.assertFalse(self.ui._replay_autoplay_timer.isActive())
        self.assertEqual(self.live_state(), before)
        dialog.close()
        dialog.deleteLater()

    def test_repeat_and_focused_play_button_never_double_toggle(self):
        self.enter()
        shortcuts = self.ui.findChildren(QShortcut)
        self.assertEqual(len(shortcuts), 3)
        self.assertTrue(all(not shortcut.autoRepeat() for shortcut in shortcuts))
        self.ui.replay_play_button.setFocusPolicy(Qt.StrongFocus)
        self.ui.replay_play_button.setFocus()
        clicks = QSignalSpy(self.ui.replay_play_button.clicked)
        self.key(Qt.Key_Space)
        self.assertEqual(len(clicks), 1)
        self.assertTrue(self.ui._replay_autoplay_timer.isActive())
        for _ in range(4):
            for kind in (QEvent.KeyPress, QEvent.KeyRelease):
                event = QKeyEvent(kind, Qt.Key_Space, Qt.NoModifier, ' ', True, 1)
                QApplication.sendEvent(self.ui, event)
        self.assertEqual(len(clicks), 1)
        self.key(Qt.Key_Space)
        self.assertEqual(len(clicks), 2)
        self.assertFalse(self.ui._replay_autoplay_timer.isActive())

    def test_shortcut_switches_back_to_live_and_is_inert_after_close(self):
        self.enter()
        self.key(Qt.Key_Space)
        self.ui.on_exit_replay()
        self.focus_board()
        self.assertFalse(self.ui._replay_mode)
        self.assertFalse(self.ui._replay_autoplay_timer.isActive())
        self.assertFalse(self.ui.live_policy_combo.isHidden())
        with patch.object(self.engine, 'reset', wraps=self.engine.reset) as reset:
            self.key(Qt.Key_Space)
        reset.assert_called_once_with()
        self.ui.close()
        before = self.live_state()
        for shortcut in self.ui.findChildren(QShortcut):
            shortcut.activated.emit()
        self.ui.on_reset()
        self.assertEqual(self.live_state(), before)
