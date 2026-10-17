"""Bounded synthetic offscreen inspection; no official DB or solver fixtures."""

import ast
from contextlib import ExitStack, redirect_stderr
from dataclasses import replace
from fractions import Fraction
import inspect
import io
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from qt_bootstrap import configure_qt_plugin_path
configure_qt_plugin_path()

from PyQt5.QtCore import QPoint, Qt, QTimer
from PyQt5.QtGui import QFontDatabase
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QLabel

import benchmark_modeled_time as modeled
from core_engine import Action, CellState, GameStatus, MinesweeperEngine
from exemplar_board_evidence import AcceptedExemplarEvidence, ExemplarReference, LoadedExemplar
import exemplar_board_evidence as evidence_module
from exemplar_board_reconstruction import reconstruct_board
import exemplar_board_reconstruction as reconstruction_module
import exemplar_board_viewer_ui as ui
from scripts import exemplar_board_viewer as launcher
from telemetry_model import InferenceCategory
import telemetry_repository
import timeline_analytics
from tests import test_exemplar_board_reconstruction as fixtures


RISK = Fraction(10**50 + 1, 3 * 10**50)


def synthetic_evidence():
    """Real immutable models from hand-written inputs on small synthetic boards."""
    fixture = fixtures.ExemplarBoardReconstructionTests()
    fixture.evaluation = modeled.authenticate_model_c()
    board, stage3 = fixture.win()
    safe = [(0, 0), (1, 0), (0, 1), (2, 0), (2, 1), (0, 2), (1, 2), (2, 2)]
    events = [fixtures.event(0, Action.OPEN, 0, 0, safe=1),
              fixtures.event(1, Action.FLAG, 1, 1, flag=1)]
    for x, y in safe[1:]:
        events.append(fixtures.event(len(events), Action.OPEN, x, y, safe=1,
            status=GameStatus.WON if (x, y) == safe[-1] else GameStatus.PLAYING))
    events[2] = replace(events[2], inference_category=InferenceCategory.PROBABILITY_GUESS,
                        target_mine_probability=RISK, minimum_available_mine_probability=Fraction(1, 3),
                        selection_candidate_count=4, decision_compute_ns=0)
    stage2 = fixture.timeline(board, tuple(events))
    s3_events = [item.event for item in stage3.actions]
    s3_events[3] = replace(s3_events[3], inference_category=InferenceCategory.PROBABILITY_GUESS,
                          target_mine_probability=RISK, minimum_available_mine_probability=Fraction(1, 3),
                          decision_compute_ns=0)
    stage3 = fixture.timeline(board, tuple(s3_events))
    loss_board, loss = fixture.loss()
    flood_board, flood = fixture.flood_clear()
    auto_events = tuple(fixtures.event(i, Action.OPEN, x, y, safe=1,
        status=GameStatus.WON if i == len(safe) - 1 else GameStatus.PLAYING)
        for i, (x, y) in enumerate(safe))
    auto = fixture.timeline(board, auto_events)
    games = []
    for index, snapshot, s2, s3 in ((10, board, stage2, stage3), (20, loss_board, loss, loss),
                                    (30, flood_board, flood, flood), (40, board, auto, auto)):
        s2, s3 = (replace(timeline, record=replace(timeline.record, game_index=index, seed=index))
                  for timeline in (s2, s3))
        reference = ExemplarReference(index, f'Synthetic <category> {index}', s2.record.board_fingerprint,
            len(s2.actions), len(s3.actions), s2.total_modeled_us, s3.total_modeled_us, s2.record.result)
        games.append(LoadedExemplar(reference, snapshot, reconstruct_board(snapshot, s2),
                                    reconstruct_board(snapshot, s3)))
    return AcceptedExemplarEvidence((), (), fixture.evaluation, tuple(games),
                                    'synthetic-source', False, 'synthetic-python', 'synthetic-architecture')


class ViewerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        # Windows' offscreen plugin has no system-font discovery. Register a
        # system font in this test process so pixel checks actually draw glyphs.
        cls._test_font_id = -1
        if sys.platform == 'win32' and not QFontDatabase().families():
            font = Path(os.environ['WINDIR']) / 'Fonts' / 'arial.ttf'
            cls._test_font_id = QFontDatabase.addApplicationFont(str(font))
            if cls._test_font_id < 0:
                raise RuntimeError('Offscreen pixel verification requires the system Arial font.')
        cls.bundle = synthetic_evidence()

    @classmethod
    def tearDownClass(cls):
        if cls._test_font_id >= 0:
            QFontDatabase.removeApplicationFont(cls._test_font_id)

    def setUp(self):
        self.window = ui.ExemplarBoardViewerWindow(self.bundle)
        self.window.show()
        self.app.processEvents()
        self.addCleanup(self.cleanup_window)

    def cleanup_window(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def texts(self, values):
        return {name: label.text() for name, label in values.items()}

    def cell_state(self, cell):
        return (cell.logical_state, cell.text(), cell.styleSheet(), cell.toolTip(),
                cell.accessibleName(), cell.accessibleDescription(), cell.answer_layer.glyph)

    def assert_frame(self):
        frame = self.window.reconstruction.frames[self.window.position.frame_index]
        for (x, y), cell in self.window.board.cells.items():
            self.assertEqual(cell.logical_state, frame.observation[y][x])
        self.assertIn(frame.status.name, self.window.status_label.text())

    def focus_entry(self, entry):
        self.window.activateWindow()
        QTest.mouseClick(entry.lineEdit(), Qt.LeftButton)
        self.app.processEvents()
        self.assertTrue(entry.hasFocus() or entry.lineEdit().hasFocus())

    def type_entry(self, entry, text):
        self.focus_entry(entry)
        QTest.keyClick(entry.lineEdit(), Qt.Key_A, Qt.ControlModifier)
        QTest.keyClicks(entry.lineEdit(), text)
        self.app.processEvents()

    def click_answer_checkbox(self):
        checkbox = self.window.answer_checkbox
        QTest.mouseClick(checkbox, Qt.LeftButton, pos=QPoint(8, checkbox.height() // 2))
        self.app.processEvents()
        self.assertTrue(checkbox.hasFocus())

    def test_input_requires_exact_bundle_family_and_four_distinct_games(self):
        for value in (None, object(), self.bundle.exemplars, replace(self.bundle, exemplars=()),
                      replace(self.bundle, exemplars=(self.bundle.exemplars[0],) * 4)):
            with self.subTest(value=type(value)), self.assertRaises(ValueError):
                ui.ExemplarBoardViewerWindow(value)

    def test_four_game_two_solver_choices_and_exact_bundle_retained(self):
        self.assertIs(self.window.evidence, self.bundle)
        self.assertEqual([self.window.game_selector.itemData(i) for i in range(4)], [10, 20, 30, 40])
        self.assertEqual(self.window.solver_selector.count(), 2)
        self.assertFalse(self.window.game_selector.isEditable())
        self.assertEqual(len(self.window._positions), 8)

    def test_all_eight_positions_start_at_initial_frame(self):
        for game in self.bundle.exemplars:
            for solver in ('stage2', 'stage3'):
                self.window.select_pair(game.reference.game_index, solver)
                self.assertEqual(self.window.position.frame_index, 0)
                self.assertIsNone(self.window.position.action_ordinal)
                self.assertEqual(self.window.action_label.text(), 'Selected action = none')
                self.assert_frame()

    def test_all_eight_positions_restore_exact_action_and_side(self):
        expected = {}
        for i, pair in enumerate(self.window._positions):
            self.window.select_pair(*pair)
            j = min(1 + i, self.window.action_count)
            self.window.select_action(j)
            self.window.set_before(bool(i % 2))
            expected[pair] = self.window.position
        for pair in reversed(expected):
            self.window.select_pair(*pair)
            self.assertEqual(self.window.position, expected[pair])
            self.assert_frame()
        # S2's index 9 is not clamped when visiting S3's shorter stream.
        self.window.select_pair(10, 'stage2')
        self.window.select_frame(9)
        self.window.select_pair(10, 'stage3')
        self.assertEqual(self.window.action_count, 8)
        self.window.select_pair(10, 'stage2')
        self.assertEqual(self.window.position.frame_index, 9)

    def test_selector_widgets_restore_positions(self):
        self.window.select_action(3)
        self.window.set_before(True)
        self.window.solver_selector.setCurrentIndex(1)
        self.window.select_frame(5)
        self.window.game_selector.setCurrentIndex(1)
        self.assertEqual(self.window.position.frame_index, 0)
        self.window.game_selector.setCurrentIndex(0)
        self.assertEqual(self.window.position.frame_index, 5)
        self.window.solver_selector.setCurrentIndex(0)
        self.assertEqual(self.window.position.action_ordinal, 3)
        self.assertTrue(self.window.position.before)

    def test_first_previous_next_last_and_boundary_buttons(self):
        w = self.window
        self.assertFalse(w.first_button.isEnabled())
        self.assertFalse(w.previous_button.isEnabled())
        self.assertFalse(w.before_button.isEnabled())
        self.assertFalse(w.after_button.isEnabled())
        w.next_button.click()
        self.assertEqual(w.position.frame_index, 1)
        w.last_button.click()
        self.assertEqual(w.position.frame_index, w.action_count)
        self.assertFalse(w.next_button.isEnabled())
        self.assertFalse(w.last_button.isEnabled())
        w.previous_button.click()
        self.assertEqual(w.position.frame_index, w.action_count - 1)
        w.first_button.click()
        self.assertIsNone(w.position.action_ordinal)

    def test_frame_slider_and_direct_entries(self):
        w = self.window
        self.assertEqual((w.frame_slider.minimum(), w.frame_slider.maximum()), (0, 9))
        w.frame_slider.setValue(4)
        self.assertEqual((w.position.action_ordinal, w.position.before), (4, False))
        self.type_entry(w.frame_entry, '2')
        self.assertEqual(w.position.frame_index, 4)
        QTest.mouseClick(w.frame_go, Qt.LeftButton)
        self.app.processEvents()
        self.assertEqual(w.position.frame_index, 2)
        self.type_entry(w.action_entry, '6')
        self.assertEqual(w.position.action_ordinal, 2)
        QTest.mouseClick(w.action_go, Qt.LeftButton)
        self.app.processEvents()
        self.assertEqual(w.position.action_ordinal, 6)

    def test_initial_action_entry_focus_loss_by_click_preserves_initial(self):
        w = self.window
        position = w.position
        self.focus_entry(w.action_entry)
        self.click_answer_checkbox()
        self.assertEqual(w.position, position)
        self.assertIsNone(w.position.action_ordinal)
        self.assertEqual(w.position.frame_index, 0)

    def test_before_action_frame_entry_focus_loss_preserves_selected_action_and_side(self):
        w = self.window
        w.select_action(3)
        w.set_before(True)
        position = w.position
        self.focus_entry(w.frame_entry)
        self.click_answer_checkbox()
        self.assertEqual(w.position, position)
        self.assertEqual((w.position.action_ordinal, w.position.before, w.position.frame_index), (3, True, 2))

    def test_initial_action_entry_tab_away_preserves_initial(self):
        w = self.window
        position = w.position
        self.focus_entry(w.action_entry)
        QTest.keyClick(w.action_entry, Qt.Key_Tab)
        self.app.processEvents()
        self.assertFalse(w.action_entry.hasFocus() or w.action_entry.lineEdit().hasFocus())
        self.assertEqual(w.position, position)

    def test_frame_entry_return_and_enter_interpret_text_and_commit_once(self):
        w = self.window
        for key in (Qt.Key_Return, Qt.Key_Enter):
            with self.subTest(key=key):
                w.select_frame(0)
                self.type_entry(w.frame_entry, '4')
                self.assertFalse(w.frame_entry.keyboardTracking())
                self.assertEqual(w.frame_entry.value(), 0)
                self.assertIsNone(w.position.action_ordinal)
                with patch.object(w, 'select_frame', wraps=w.select_frame) as select:
                    QTest.keyClick(w.frame_entry.lineEdit(), key)
                    self.app.processEvents()
                select.assert_called_once_with(4)
                self.assertEqual((w.position.action_ordinal, w.position.before), (4, False))

    def test_action_entry_return_and_enter_interpret_text_and_commit_once(self):
        w = self.window
        for key in (Qt.Key_Return, Qt.Key_Enter):
            with self.subTest(key=key):
                w.select_frame(0)
                self.type_entry(w.action_entry, '3')
                self.assertFalse(w.action_entry.keyboardTracking())
                self.assertEqual(w.action_entry.value(), 1)
                self.assertIsNone(w.position.action_ordinal)
                with patch.object(w, 'select_action', wraps=w.select_action) as select:
                    QTest.keyClick(w.action_entry.lineEdit(), key)
                    self.app.processEvents()
                select.assert_called_once_with(3)
                self.assertEqual((w.position.action_ordinal, w.position.before), (3, False))

    def test_uncommitted_edited_text_focus_loss_does_not_navigate(self):
        w = self.window
        for entry in (w.frame_entry, w.action_entry):
            with self.subTest(entry=entry):
                w.select_frame(0)
                position = w.position
                self.type_entry(entry, '3')
                self.click_answer_checkbox()
                self.assertEqual(w.position, position)

    def test_navigation_button_after_entry_focus_loss_navigates_only_once(self):
        w = self.window
        self.focus_entry(w.action_entry)
        with patch.object(w, 'select_frame', wraps=w.select_frame) as select:
            QTest.mouseClick(w.next_button, Qt.LeftButton)
            self.app.processEvents()
        select.assert_called_once_with(1)
        self.assertEqual((w.position.action_ordinal, w.position.before), (1, False))

    def test_before_after_labels_and_frame_navigation_semantics(self):
        w = self.window
        w.select_action(3)
        w.before_button.click()
        self.assertEqual((w.position.action_ordinal, w.position.frame_index), (3, 2))
        self.assertIn('Displayed frame 2 / 9', w.frame_label.text())
        self.assertIn('Selected action 3 / 9', w.action_label.text())
        self.assertIn('not yet applied', w.inspection_label.text())
        self.assertFalse(w.before_button.isEnabled())
        self.assertTrue(w.after_button.isEnabled())
        w.after_button.click()
        self.assertEqual(w.position.frame_index, 3)
        w.before_button.click()
        w.previous_button.click()
        self.assertEqual((w.position.action_ordinal, w.position.before), (1, False))
        w.select_action(3)
        w.before_button.click()
        w.next_button.click()
        self.assertEqual((w.position.action_ordinal, w.position.before), (3, False))

    def test_before_first_is_distinct_from_initial_and_first_restores_initial(self):
        w = self.window
        w.select_action(1)
        w.set_before(True)
        self.assertEqual(w.position.frame_index, 0)
        self.assertIn('Selected recorded action 1 — not yet applied', w.inspection_label.text())
        self.assertEqual(w.action_values['Action type'].text(), 'OPEN')
        self.assertTrue(w.first_button.isEnabled())
        self.assertFalse(w.previous_button.isEnabled())
        w.first_button.click()
        self.assertIsNone(w.position.action_ordinal)
        self.assertEqual(w.action_values['Action type'].text(), 'unavailable')
        w.select_action(1)
        w.set_before(True)
        w.frame_go.click()  # Already showing spin value 0; explicit Go still resets.
        self.assertIsNone(w.position.action_ordinal)

    def test_invalid_nonwidget_inputs_fail_without_changing_position(self):
        w = self.window
        for method, values in ((w.select_frame, (-1, 10, True, 1.0, '1', None)),
                               (w.select_action, (0, 10, False, 1.0, '1', None)),
                               (w.set_before, (0, 1, 'before', None))):
            for value in values:
                with self.subTest(method=method.__name__, value=value), self.assertRaises(ValueError):
                    method(value)
        for pair in ((True, 'stage2'), (999, 'stage2'), (10, 'other'), ('10', 'stage2')):
            with self.assertRaises(ValueError):
                w.select_pair(*pair)
        self.assertIsNone(w.position.action_ordinal)

    def test_every_stored_frame_is_rendered_by_lookup(self):
        for game in self.bundle.exemplars:
            for solver in ('stage2', 'stage3'):
                self.window.select_pair(game.reference.game_index, solver)
                for k in range(self.window.action_count + 1):
                    self.window.select_frame(k)
                    self.assert_frame()

    def test_loss_terminal_feedback_and_before_terminal(self):
        w = self.window
        w.select_pair(20, 'stage3')
        w.last_button.click()
        states = {cell.logical_state for cell in w.board.cells.values()}
        self.assertTrue({CellState.EXPLODED, CellState.MINE, CellState.FALSE_FLAG, CellState.FLAGGED} <= states)
        self.assertIn('Terminal Engine feedback', w.status_label.text())
        self.assertEqual(w.reference_values['Final recorded outcome'].text(), 'LOSS')
        w.before_button.click()
        self.assertNotIn('Terminal Engine feedback', w.status_label.text())
        self.assertIn('PLAYING', w.status_label.text())
        self.assertEqual(w.board.cells[1, 0].logical_state, CellState.HIDDEN)
        self.assertEqual(w.reference_values['Final recorded outcome'].text(), 'LOSS')

    def test_automatic_win_flags_are_public_effects_not_extra_actions(self):
        w = self.window
        w.select_pair(40, 'stage3')
        w.last_button.click()
        self.assertEqual(w.board.cells[1, 1].logical_state, CellState.FLAGGED)
        self.assertEqual(w.action_values['Explicit flag delta'].text(), '0')
        self.assertEqual(w.position.frame_index, 8)

    def test_overlay_default_off_and_hidden_only_answers_include_blank_zero(self):
        w = self.window
        self.assertFalse(w.answer_checkbox.isChecked())
        self.assertTrue(all(not cell.answer_layer.glyph for cell in w.board.cells.values()))
        w.answer_checkbox.setChecked(True)
        self.assertEqual(w.board.cells[1, 1].answer_layer.glyph, '✹')
        self.assertEqual(w.board.cells[0, 0].answer_layer.glyph, '1')
        self.assertAlmostEqual(w.board.cells[0, 0].answer_layer.graphicsEffect().opacity(), 0.35)
        w.select_pair(30, 'stage2')
        self.assertEqual(w.board.cells[3, 2].answer_layer.glyph, '')
        self.assertEqual(w.board.cells[3, 2].logical_state, CellState.HIDDEN)

    def test_overlay_off_restores_exact_public_representation_and_pixels(self):
        w = self.window
        cell = w.board.cells[1, 1]
        before = self.cell_state(cell)
        image = cell.grab().toImage()
        w.answer_checkbox.setChecked(True)
        self.app.processEvents()
        self.assertEqual(cell.text(), '')
        self.assertEqual(cell.styleSheet(), before[2])
        self.assertNotEqual(cell.grab().toImage(), image)
        w.answer_checkbox.setChecked(False)
        self.app.processEvents()
        self.assertEqual(self.cell_state(cell), before)
        self.assertEqual(cell.grab().toImage(), image)

    def test_overlay_never_changes_nonhidden_cells_or_metadata(self):
        w = self.window
        for game, solver, frame in ((10, 'stage3', 3), (20, 'stage2', 4), (40, 'stage3', 8)):
            w.select_pair(game, solver)
            w.select_frame(frame)
            before = {xy: self.cell_state(cell) for xy, cell in w.board.cells.items()
                      if cell.logical_state != CellState.HIDDEN}
            context, position = self.texts(w.action_values), w.position
            observation = w.reconstruction.frames[frame].observation
            w.answer_checkbox.setChecked(True)
            for xy, state in before.items():
                self.assertEqual(self.cell_state(w.board.cells[xy]), state)
            self.assertEqual(self.texts(w.action_values), context)
            self.assertEqual(w.position, position)
            self.assertIs(w.reconstruction.frames[frame].observation, observation)
            w.answer_checkbox.setChecked(False)

    def test_hidden_answers_never_enter_tooltip_or_accessibility_text(self):
        w = self.window
        before = {xy: (cell.toolTip(), cell.accessibleName(), cell.accessibleDescription())
                  for xy, cell in w.board.cells.items()}
        w.answer_checkbox.setChecked(True)
        for xy, cell in w.board.cells.items():
            self.assertEqual((cell.toolTip(), cell.accessibleName(), cell.accessibleDescription()), before[xy])
            self.assertEqual(cell.answer_layer.toolTip(), '')
            self.assertEqual(cell.answer_layer.accessibleName(), '')
            self.assertEqual(cell.answer_layer.accessibleDescription(), '')
            self.assertFalse(cell.answer_layer.findChildren(QLabel))
            self.assertNotIsInstance(cell.answer_layer, QLabel)

    def test_revealed_palette_supports_all_numbers_and_zero(self):
        cell = self.window.board.cells[0, 0]
        for value in range(9):
            cell.render_state(value, answer=-1)
            self.assertEqual(cell.text(), str(value) if value else '')
            self.assertEqual(cell.answer_layer.glyph, '')
            self.assertIn(ui.NUMBER_COLORS.get(value, '#000000'), cell.styleSheet())

    def test_new_safe_highlight_only_after_and_exact_coordinates(self):
        w = self.window
        w.select_pair(10, 'stage3')
        w.select_action(3)
        expected = w.reconstruction.newly_revealed_safe_by_action[2]
        self.assertEqual({xy for xy, cell in w.board.cells.items() if cell.newly_safe}, expected)
        w.set_before(True)
        self.assertFalse(any(cell.newly_safe for cell in w.board.cells.values()))
        self.assertEqual(w.action_values['Reconstructed new-safe count'].text(), str(len(expected)))
        w.select_frame(0)
        self.assertFalse(any(cell.newly_safe for cell in w.board.cells.values()))
        w.select_pair(20, 'stage3')
        w.last_button.click()
        self.assertFalse(any(cell.newly_safe for cell in w.board.cells.values()))

    def test_first_action_has_no_previous_target_or_origin_line(self):
        w = self.window
        w.select_action(1)
        self.assertEqual(w.board.targets.current_target, (0, 0))
        self.assertIsNone(w.board.targets.previous_target)
        self.assertIsNone(w.board.targets.transition_line)
        self.assertEqual(w.action_values['Previous recorded target'].text(), 'unavailable')
        self.assertEqual(w.model_values['Initial Model C cursor'].text(), '(0, 0)')

    def test_target_geometry_same_target_and_before_after_independence(self):
        w = self.window
        w.select_pair(10, 'stage3')
        w.select_action(2)
        self.assertEqual(w.board.targets.transition_line, ((0, 0), (1, 1)))
        self.assertEqual([w.action_values[name].text() for name in ('dx', 'dy', 'd²')], ['1', '1', '2'])
        w.set_before(True)
        self.assertEqual(w.board.targets.transition_line, ((0, 0), (1, 1)))
        w.select_action(5)
        self.assertEqual(w.board.targets.current_target, (2, 0))
        self.assertEqual(w.board.targets.previous_target, (2, 0))
        self.assertIsNone(w.board.targets.transition_line)
        self.assertEqual([w.action_values[name].text() for name in ('dx', 'dy', 'd²')], ['0', '0', '0'])
        self.assertGreater(int(w.action_values['Selected Model C action us'].text()), 0)

    def test_reference_panel_and_solver_policy_are_factual_and_plain_text(self):
        w = self.window
        game = self.bundle.exemplars[0]
        self.assertEqual(w.reference_values['Accepted category'].text(), game.reference.category)
        self.assertEqual(w.reference_values['Accepted category'].textFormat(), Qt.PlainText)
        self.assertIn('OPEN / FLAG only', w.policy_note.text())
        for name, value in (('Total 3BV', game.stage2.board_reference.total_3bv),
                            ('Total Ops', game.stage2.board_reference.total_ops),
                            ('Isolated-number count', game.stage2.board_reference.isolated_number_count)):
            self.assertEqual(w.reference_values[name].text(), str(value))
        w.select_pair(10, 'stage3')
        self.assertIn('OPEN / FLAG / CHORD', w.policy_note.text())

    def test_counter_rows_order_final_strings_and_historical_unavailability(self):
        w = self.window
        self.assertEqual(tuple(w.counter_values), ('Time','Est Time','3BV','3BV/s','Clicks','Left','Right',
            'Chord','CPS','Efficiency','IOE','Ops','Thrp','Corr','ZiNi','ZNE','ZNT'))
        for game in self.bundle.exemplars:
            w.select_pair(game.reference.game_index, 'stage3')
            final = w.reconstruction.final_counters
            for label, field in (('3BV','bbbv_text'),('Ops','ops_text'),('Clicks','clicks_text'),
                                  ('Left','left_text'),('Right','right_text'),('Chord','chord_text')):
                self.assertEqual(w.counter_values[label].text(), getattr(final, field))
            for name in ('Time', 'Est Time', '3BV/s', 'CPS'):
                self.assertEqual(w.counter_values[name].text(), '-')
                self.assertEqual(w.counter_values[name].toolTip(), 'historical elapsed time unavailable')
            initial = self.texts(w.counter_values)
            w.last_button.click()
            w.answer_checkbox.setChecked(True)
            self.assertEqual(self.texts(w.counter_values), initial)

    def test_counter_ratios_rounding_and_zero_denominators(self):
        original_game = self.bundle.exemplars[0]
        cases = (
            (3, 4, 2, ('29%', '0.2857', '0.6667', '0.4286')),
            (4, 4, 1, ('12%', '0.1250', '0.2500', '0.5000')),
            (0, 0, 0, ('-', '-', '-', '-')),
            (0, 2, 1, ('50%', '0.5000', '-', '0.0000')),
        )
        for active, wasted, b, expected in cases:
            final = replace(original_game.stage2.final_counters, active_clicks=active,
                            wasted_clicks=wasted, completed_3bv=b)
            game = replace(original_game, stage2=replace(original_game.stage2, final_counters=final))
            w = ui.ExemplarBoardViewerWindow(replace(self.bundle, exemplars=(game, *self.bundle.exemplars[1:])))
            try:
                for name, value in zip(('Efficiency', 'IOE', 'Thrp', 'Corr'), expected):
                    self.assertEqual(w.counter_values[name].text(), value)
            finally:
                w.close()
                w.deleteLater()

    def test_zini_rows_retained_and_explicitly_deferred_on_win_and_loss(self):
        self.assertEqual(ui.ZINI_NOTE,
            'Optional answer-derived ZiNi reference is not calculated in this standalone viewer.')
        for game in (10, 20):
            self.window.select_pair(game, 'stage3')
            for name in ('ZiNi', 'ZNE', 'ZNT'):
                self.assertEqual(self.window.counter_values[name].text(), '-')
                self.assertEqual(self.window.counter_values[name].toolTip(), ui.ZINI_NOTE)

    def test_model_costs_follow_displayed_frame_and_selected_action_separately(self):
        w = self.window
        timeline = w.reconstruction.timeline
        self.assertEqual(w.model_values['Selected Action Model C Cost'].text(), 'unavailable')
        self.assertEqual(w.model_values['Cumulative Model C Time'].text(), '0 us')
        w.select_action(3)
        w.set_before(True)
        self.assertEqual(w.model_values['Selected Action Model C Cost'].text(), f'{timeline.actions[2].modeled_action_us} us')
        self.assertEqual(w.model_values['Cumulative Model C Time'].text(), f'{timeline.actions[1].cumulative_modeled_us} us')
        w.set_before(False)
        self.assertEqual(w.model_values['Cumulative Model C Time'].text(), f'{timeline.actions[2].cumulative_modeled_us} us')
        w.select_action(1)
        w.set_before(True)
        self.assertEqual(w.model_values['Cumulative Model C Time'].text(), '0 us')

    def test_model_final_rates_use_completed_3bv_and_actions_over_model_seconds(self):
        w = self.window
        for game in (10, 20):
            w.select_pair(game, 'stage3')
            cost = w.reconstruction.timeline.total_modeled_us
            b = w.reconstruction.final_counters.completed_3bv
            self.assertEqual(w.model_values['Final Model C Time'].text(), f'{cost} us')
            self.assertEqual(w.model_values['Modeled 3BV/s'].text(), f'{b * 1000000}/{cost} = {b * 1000000/cost:.4f} (presentation)')
            self.assertIn(f'{w.action_count * 1000000}/{cost}', w.model_values['Modeled CPS'].text())
            if game == 20:
                self.assertIn('through termination — not time-to-win', w.cost_note.text())

    def test_exact_fraction_none_zero_and_candidate_scope(self):
        w = self.window
        w.select_action(3)
        self.assertEqual(w.action_values['Target mine probability'].text(), f'{RISK.numerator}/{RISK.denominator}')
        self.assertEqual(w.action_values['Minimum available mine probability'].text(), '1/3')
        self.assertEqual(w.action_values['Decision compute (ns)'].text(), '0')
        self.assertEqual(w.action_values['Candidate count'].text(), '4')
        w.select_pair(10, 'stage3')
        w.select_action(4)
        self.assertEqual(w.action_values['Candidate count'].text(), 'unavailable')
        w.select_action(1)
        self.assertEqual(w.action_values['Decision compute (ns)'].text(), 'unavailable')
        self.assertEqual(w.action_values['Inference category'].text(), 'unavailable')
        self.assertIn('exact-minimum-risk', ui.CANDIDATE_NOTE)
        self.assertIn('analysis + planning', ui.COMPUTE_NOTE)

    def test_initial_context_has_no_fabricated_event_facts(self):
        w = self.window
        for name in ('Selected ordinal','Action type','Current target','Previous recorded target',
                     'dx','dy','d²','Selected Model C action us','Inference category','Target mine probability',
                     'Candidate count','Decision compute (ns)','Recorded safe reveal delta',
                     'Reconstructed new-safe count','Explicit flag delta'):
            self.assertEqual(w.action_values[name].text(), 'unavailable')
        self.assertEqual(w.action_values['Displayed frame'].text(), '0')
        self.assertEqual(w.action_values['Cumulative Model C us'].text(), '0')
        self.assertIsNone(w.board.targets.current_target)

    def test_board_mouse_input_does_not_play_or_navigate(self):
        position = self.window.position
        for button in (Qt.LeftButton, Qt.RightButton, Qt.MiddleButton):
            QTest.mouseClick(self.window.board.cells[0, 0], button)
        self.assertEqual(self.window.position, position)
        self.assert_frame()

    def test_five_areas_and_scroll_containers_remain_available_on_small_window(self):
        from PyQt5.QtWidgets import QGroupBox
        titles = [group.title() for group in self.window.findChildren(QGroupBox)]
        self.assertCountEqual(titles, [
            'Board / Solver Reference', 'Classic Counters / Final Run Summary',
            'Model C', 'Action Context', 'Board Presentation — Public View',
        ])
        self.window.resize(800, 600)
        self.app.processEvents()
        self.assertIs(self.window.board_scroll.widget(), self.window.board)
        self.assertTrue(self.window.sidebar_scroll.widgetResizable())
        self.assertEqual(self.window.board.width(), self.window.reconstruction.board_snapshot.width * 28)

    def test_authority_labels_preserve_exact_semantic_boundaries(self):
        texts = [label.text() for label in self.window.findChildren(QLabel)]
        self.assertIn('Reconstructed Counters — current Engine semantics; FINAL RUN SUMMARY', texts)
        self.assertIn('Historical elapsed time unavailable. Mechanical active/wasted '
                      'classification is not strategic quality.', texts)
        self.assertIn('3BV / Ops / isolated number count = answer-derived board references, '
                      'not solver-visible evidence.', texts)
        self.assertEqual(self.window.answer_checkbox.text(), 'Show hidden answers — reference overlay')
        self.assertEqual(ui.TRANSITION_NOTE, 'Action-target transition — not recorded cursor trajectory')
        self.assertIn('Action-target transition — not recorded cursor trajectory. Orange outline: '
                      'selected target; blue ring: previous recorded target; green: newly revealed safe cells AFTER.', texts)
        model_note = (
            'Both timelines are post-hoc Model C evaluations of persisted actions. '
            'Stage 2 did not natively declare Model C; Stage 3 declared it during collection, '
            'but these events retain no native per-action cost/cursor fields. '
            'This is modeled physical execution time, not Replay elapsed, CPU decision '
            'time or recorded cursor trajectory.'
        )
        self.assertEqual(ui.MODEL_NOTE, model_note)
        self.assertIn(model_note, texts)

    def test_construction_navigation_and_toggles_do_no_domain_work(self):
        with ExitStack() as guards:
            for owner, name in ((evidence_module,'load_accepted_exemplar_evidence'),
                                (evidence_module.boards,'generate_board'),
                                (telemetry_repository,'connect_database_readonly'),
                                (telemetry_repository,'connect_database'),
                                (MinesweeperEngine,'__init__'), (MinesweeperEngine,'step'),
                                (MinesweeperEngine,'reset_with_mines'),
                                (reconstruction_module,'reconstruct_board'),
                                (timeline_analytics,'project_timeline'),
                                (modeled,'authenticate_model_c')):
                guards.enter_context(patch.object(owner, name, side_effect=AssertionError(name)))
            window = ui.ExemplarBoardViewerWindow(self.bundle)
            try:
                for pair in window._positions:
                    window.select_pair(*pair)
                    window.select_frame(window.action_count)
                    window.set_before(True)
                    window.answer_checkbox.setChecked(True)
                    window.answer_checkbox.setChecked(False)
                self.assertEqual(window.findChildren(QTimer), [])
            finally:
                window.close()
                window.deleteLater()

    def test_no_forbidden_ui_imports_or_clock_execution_paths(self):
        tree = ast.parse(inspect.getsource(ui))
        forbidden = {'sqlite3','telemetry_repository','benchmark_board','benchmark_modeled_time',
                     'timeline_analytics','simple_runner','simple_decision','stage3_runner','stage3_planner',
                     'representative_boards','ui_manager','zini_explorer','zini_calculator',
                     'stage3_visualizer_ui','same_board_comparison_ui','subprocess','time'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertTrue(all(a.name.split('.')[0] not in forbidden for a in node.names))
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn(node.module.split('.')[0], forbidden)
                self.assertTrue(all(a.name not in ('MinesweeperEngine','QTimer','load_accepted_exemplar_evidence') for a in node.names))


class LauncherTests(unittest.TestCase):
    def test_both_paths_required_and_arbitrary_options_rejected(self):
        for args in ([], ['--stage2-db','s2'], ['--stage3-db','s3'],
                     ['--stage2-db','s2','--stage3-db','s3','--game-index','10']):
            with self.subTest(args=args), redirect_stderr(io.StringIO()), \
                    patch.object(launcher,'load_accepted_exemplar_evidence') as load, \
                    self.assertRaises(SystemExit) as raised:
                launcher.main(args)
            self.assertEqual(raised.exception.code, 2)
            load.assert_not_called()

    def test_one_loader_call_correct_roles_exact_bundle_then_show_and_event_loop(self):
        bundle, calls = object(), []
        app, window = MagicMock(), MagicMock()
        app.exec_.return_value = 7
        with patch.object(launcher,'load_accepted_exemplar_evidence', side_effect=lambda *args: calls.append('load') or bundle) as load, \
                patch.object(launcher,'QApplication') as app_type, \
                patch.object(launcher,'ExemplarBoardViewerWindow', side_effect=lambda data: calls.append('window') or window) as viewer:
            app_type.instance.return_value = None
            app_type.return_value = app
            self.assertEqual(launcher.main(['--stage2-db','s2 #%.sqlite3','--stage3-db','s3.sqlite3']), 7)
        load.assert_called_once_with(Path('s2 #%.sqlite3'), Path('s3.sqlite3'))
        viewer.assert_called_once_with(bundle)
        window.show.assert_called_once()
        app.exec_.assert_called_once()
        app_type.assert_called_once()
        self.assertEqual(calls, ['load','window'])

    def test_existing_application_is_reused(self):
        app = MagicMock()
        app.exec_.return_value = 0
        with patch.object(launcher,'load_accepted_exemplar_evidence'), \
                patch.object(launcher,'ExemplarBoardViewerWindow'), patch.object(launcher,'QApplication') as app_type:
            app_type.instance.return_value = app
            self.assertEqual(launcher.main(['--stage2-db','s2','--stage3-db','s3']), 0)
            app_type.assert_not_called()

    def test_load_failure_reports_and_creates_no_qapplication_or_viewer(self):
        output = io.StringIO()
        with patch.object(launcher,'load_accepted_exemplar_evidence', side_effect=launcher.ExemplarEvidenceError('hash mismatch')), \
                patch.object(launcher,'QApplication') as app, patch.object(launcher,'ExemplarBoardViewerWindow') as viewer, \
                redirect_stderr(output):
            self.assertEqual(launcher.main(['--stage2-db','s2','--stage3-db','s3']), 1)
        self.assertIn('Cannot load accepted exemplar evidence: hash mismatch', output.getvalue())
        app.assert_not_called()
        app.instance.assert_not_called()
        viewer.assert_not_called()


if __name__ == '__main__':
    unittest.main()
