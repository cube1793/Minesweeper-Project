"""Real offscreen Qt coverage for the separate, index-only ZiNi Explorer.

Recorded small paths exercise presentation without running a search. The main
UI tests deliver the unchanged worker envelope through the real polling path.
"""

import ast
from contextlib import ExitStack
from dataclasses import replace
import os
from pathlib import Path
import time
import unittest

from tests.ui_settings import isolate_ui_settings
from unittest.mock import Mock, patch

# Bootstrap precedes every PyQt import as well as QApplication construction.
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from qt_bootstrap import configure_qt_plugin_path

configure_qt_plugin_path()
try:
    from PyQt5.QtCore import QEvent, QPoint, QPointF, Qt, QRect
    from PyQt5.QtGui import QMouseEvent, QPalette
    from PyQt5.QtTest import QTest
    from PyQt5.QtWidgets import QApplication, QLabel, QScrollArea, QStyle, QStyleOptionSlider
except ImportError:
    QApplication = None
else:
    import zini_explorer_ui
    from core_engine import Action, GameStatus, MinesweeperEngine
    from replay_model import ACTION_OPEN, ReplayBoard, ReplayData, ReplayEvent
    from replay_player import ReplayPlayer
    from ui_manager import MinesweeperUI, NUMBER_COLORS
    from zini_explorer_ui import ZiniExplorerWindow
    from zini_metric_worker import write_result_atomic

from board_snapshot import BoardSnapshot
from zini_calculator import ZiniMove, ZiniResult
from zini_explorer import ZiniExplorerController
from zini_trace import ZiniTraceSelection, build_zini_trace


ROOT = Path(__file__).resolve().parents[1]
CENTER_SNAPSHOT = BoardSnapshot(
    3, 3, 1, True, frozenset({(1, 1)}),
    ((1, 1, 1), (1, 0, 1), (1, 1, 1)),
)
CENTER_RESULT = ZiniResult(5, (
    ZiniMove("click", 1, 0, 2, 1),
    ZiniMove("flag_chord", 1, 0, 2, 2),
    ZiniMove("flag_chord", 0, 1, 1, 1),
    ZiniMove("flag_chord", 2, 1, 0, 1),
))
FALLBACK_SNAPSHOT = BoardSnapshot(3, 1, 1, True, {(1, 0)}, ((1, 0, 1),))
FALLBACK_RESULT = ZiniResult(2, (
    ZiniMove("fallback_click", 2, 0, None, 1),
    ZiniMove("fallback_click", 0, 0, None, 1),
))


def payload(token, result=CENTER_RESULT, **changes):
    return {"token": token, "clicks": result.clicks, "moves": result.moves,
            "error": None, **changes}


def ready_controller(snapshot=CENTER_SNAPSHOT, result=CENTER_RESULT):
    controller = ZiniExplorerController()
    controller.begin(7, snapshot, eligible=True)
    controller.receive(payload(7, result), expected_token=7)
    if controller.request_trace() is None:
        raise AssertionError(controller.error)
    return controller


def forbid_search(stack):
    for target in (
        "zini_calculator.calculate_g_zini",
        "zini_calculator.calculate_g_zini_min_ties_bounded",
        "zini_calculator.calculate_g_zini_neighborhood_beam_bounded",
        "zini_min_ties._MinTieSearch.find_best_moves",
        "zini_advanced._NeighborhoodBeamSearch.run",
        "ui_manager.subprocess.Popen",
    ):
        stack.enter_context(patch(target, side_effect=AssertionError(target)))


@unittest.skipIf(QApplication is None, "PyQt5 unavailable")
class ExplorerWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.controller = ready_controller()
        self.windows = []
        self.addCleanup(self.close_windows)
        self.window = self.create_window(self.controller)

    def create_window(self, controller):
        window = ZiniExplorerWindow(controller)
        self.windows.append(window)
        return window

    def close_windows(self):
        for window in self.windows:
            try:
                window.close()
            except RuntimeError:  # WA_DeleteOnClose may already have run.
                pass
        self.app.processEvents()

    def test_module_has_only_presentation_dependencies(self):
        module = ast.parse((ROOT / "zini_explorer_ui.py").read_text(encoding="utf-8"))
        allowed = {"__future__", "PyQt5", "board_snapshot", "zini_explorer", "zini_trace"}
        for node in ast.walk(module):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                self.assertIn(name.split(".")[0], allowed, name)
        for forbidden in ("MinesweeperEngine", "ReplayPlayer", "ReplayData",
                          "ReplayStatisticsAnalyzer", "_replay_mode",
                          "_engine_for_current_mode", "render_board"):
            self.assertNotIn(forbidden, vars(zini_explorer_ui))

    def test_trace_ready_construction_and_navigation_never_rebuild_or_search(self):
        trace = self.controller.trace
        with ExitStack() as stack:
            forbid_search(stack)
            for target in ("zini_explorer.build_zini_trace", "zini_trace._build_premium_context",
                           "zini_trace._find_premium_candidates"):
                stack.enter_context(patch(target, side_effect=AssertionError(target)))
            stack.enter_context(patch.object(
                self.controller, "request_trace", side_effect=AssertionError("lazy boundary"),
            ))
            window = self.create_window(self.controller)
            self.assertTrue(window.isWindow())
            self.assertTrue(window.testAttribute(Qt.WA_DeleteOnClose))
            window.last_button.click()
            window.first_button.click()
            window.slider.setValue(2)
        self.assertIs(self.controller.trace, trace)
        self.assertEqual(self.controller.current_index, 2)

    def test_constructor_requires_an_eligible_already_built_trace(self):
        controller = ZiniExplorerController()
        controller.begin(8, CENTER_SNAPSHOT, eligible=True)
        with patch("zini_explorer.build_zini_trace") as build:
            with self.assertRaises(ValueError):
                ZiniExplorerWindow(controller)
            controller.receive(payload(8), expected_token=8)
            with self.assertRaises(ValueError):
                ZiniExplorerWindow(controller)
        build.assert_not_called()
        controller.request_trace()
        controller.set_eligible(False)
        with self.assertRaises(ValueError):
            ZiniExplorerWindow(controller)

    def test_initial_board_is_closed_without_flags_diagnostics_or_highlights(self):
        self.assertEqual(len(self.window.cells), 9)
        self.assertTrue(self.window.findChildren(QScrollArea))
        self.assertEqual(self.controller.current_index, 0)
        self.assertEqual(self.controller.step_count, 4)
        self.assertEqual(self.window.clicks_label.text(), "Clicks 0 / 5")
        for cell in self.window.cells.values():
            self.assertEqual(cell.state, "closed")
            self.assertEqual(cell.text(), "")
            self.assertFalse(cell.selected or cell.newly_revealed or cell.newly_flagged)
        for key, label in self.window.diagnostic_labels.items():
            if key != "tie_count":
                self.assertEqual(label.text(), "—", key)

    def test_answer_display_defaults_on_for_each_new_window(self):
        checkbox = self.window.answer_display_checkbox
        self.assertEqual(checkbox.text(), "미공개 정답 표시")
        self.assertTrue(checkbox.isChecked())
        self.window.slider.setValue(2)
        checkbox.click()
        self.assertFalse(checkbox.isChecked())
        self.window.close()
        reopened = self.create_window(self.controller)
        self.assertTrue(reopened.answer_display_checkbox.isChecked())
        self.assertEqual(self.controller.current_index, 2)

    def assert_covered_answer(self, cell, text, color):
        self.assertEqual(cell.state, "closed")
        self.assertEqual(cell.property("state"), "closed")
        self.assertEqual(cell.text(), "")
        self.assertIn("background-color: #c0c0c0", cell.styleSheet())
        self.assertIn("border: 2px outset #ffffff", cell.styleSheet())
        self.assertEqual(cell.answer_label.text(), text)
        self.assertFalse(cell.answer_label.isHidden())
        self.assertIn(color, cell.answer_label.styleSheet())
        self.assertIn("background-color: transparent", cell.answer_label.styleSheet())
        self.assertIn("border: none", cell.answer_label.styleSheet())
        self.assertIsNone(cell.graphicsEffect())
        opacity = cell.answer_label.graphicsEffect().opacity()
        self.assertGreater(opacity, 0)
        self.assertLessEqual(opacity, 0.5)

    def test_unopened_number_is_faint_but_stays_covered_at_initial_and_early_step(self):
        for index in (0, 1):
            with self.subTest(index=index):
                self.window.slider.setValue(index)
                self.assert_covered_answer(self.window.cells[(0, 0)], "1", NUMBER_COLORS[1])
                self.assertNotIn((0, 0), self.controller.revealed)

    def test_unopened_answer_matches_revealed_number_font_and_color_after_polish(self):
        window = self.window
        self.show_on_screen(window, QRect(0, 0, 1920, 1080))
        window.next_button.click()
        revealed = window.cells[(1, 0)]
        covered = window.cells[(0, 0)]
        for enabled in (True, False, True):
            window.answer_display_checkbox.setChecked(enabled)
            self.app.processEvents()
            answer_font, revealed_font = covered.answer_label.font(), revealed.font()
            self.assertEqual(answer_font.family(), revealed_font.family())
            self.assertEqual(answer_font.pointSizeF(), revealed_font.pointSizeF())
            self.assertEqual(answer_font.pixelSize(), revealed_font.pixelSize())
            self.assertEqual(answer_font.weight(), revealed_font.weight())
            self.assertEqual(answer_font.bold(), revealed_font.bold())
            self.assertTrue(answer_font.bold())
            self.assertEqual(answer_font, revealed_font)
            self.assertEqual(covered.answer_label.palette().color(QPalette.WindowText),
                             revealed.palette().color(QPalette.WindowText))
            self.assertAlmostEqual(covered.answer_label.graphicsEffect().opacity(), 0.35)
            self.assertEqual(covered.state, "closed")
            self.assertEqual(revealed.state, "revealed")
            self.assertEqual(covered.answer_label.isHidden(), not enabled)
            if enabled:
                self.assert_covered_answer(covered, revealed.text(), NUMBER_COLORS[1])

    def test_unopened_mine_is_faint_but_stays_covered_at_initial_and_early_step(self):
        for index in (0, 1):
            with self.subTest(index=index):
                self.window.slider.setValue(index)
                self.assert_covered_answer(self.window.cells[(1, 1)], "💣", "#000000")
                self.assertNotIn((1, 1), self.controller.flagged_mines)

    def test_answer_toggle_off_restores_old_hidden_style_and_on_restores_answers(self):
        window = self.window
        answers = {coord: (cell.answer_label.text(), cell.answer_label.styleSheet())
                   for coord, cell in window.cells.items()}
        for enabled in (False, True, False, True):
            window.answer_display_checkbox.click()
            self.assertEqual(window.answer_display_checkbox.isChecked(), enabled)
            for coord, cell in window.cells.items():
                self.assertEqual(cell.state, "closed")
                self.assertEqual(cell.text(), "")
                self.assertEqual(cell.styleSheet(),
                                 "QLabel { background-color: #c0c0c0; color: #000000;"
                                 " border: 2px outset #ffffff; margin: 0px; padding: 0px; }")
                self.assertEqual(cell.answer_label.isHidden(), not enabled)
                self.assertEqual(cell.answer_label.text(), answers[coord][0] if enabled else "")
                if enabled:
                    self.assertEqual(cell.answer_label.styleSheet(), answers[coord][1])

    def test_revealed_and_flagged_rendering_is_identical_in_both_display_modes(self):
        window = self.window
        for index in range(1, self.controller.step_count + 1):
            window.slider.setValue(index)
            normal = {coord: (cell.text(), cell.styleSheet(), cell.selected,
                              cell.newly_revealed, cell.newly_flagged)
                      for coord, cell in window.cells.items() if cell.state != "closed"}
            for enabled in (False, True):
                window.answer_display_checkbox.setChecked(enabled)
                for coord, expected in normal.items():
                    cell = window.cells[coord]
                    self.assertEqual((cell.text(), cell.styleSheet(), cell.selected,
                                      cell.newly_revealed, cell.newly_flagged), expected)
                    self.assertTrue(cell.answer_label.isHidden())
                    self.assertEqual(cell.answer_label.text(), "")
                    if cell.state == "flagged":
                        self.assertEqual(cell.text(), "🚩")
                        self.assertIn("color: #c00000", cell.styleSheet())
                        self.assertIn("border: 2px outset #ffffff", cell.styleSheet())
                    else:
                        self.assertEqual(cell.text(), "1")
                        self.assertIn(NUMBER_COLORS[1], cell.styleSheet())

    def test_answer_toggle_only_renders_board_without_state_changes_or_zini_work(self):
        window, controller = self.window, self.controller
        fields = ("token", "state", "eligible", "completed", "snapshot", "clicks", "moves",
                  "trace", "current_index", "current_step", "step_count", "cumulative_clicks",
                  "revealed", "flagged_mines", "worker_error", "trace_error")
        for index in (0, 1, 2, 4):
            window.slider.setValue(index)
            window.interval_spin.setValue(5000)
            window.play_button.click()
            before = tuple(getattr(controller, field) for field in fields)
            player = controller._player
            trace, moves = controller.trace, controller.moves
            player_before = (player.current_index, player.revealed, player.flagged_mines)
            ui_before = (window.slider.value(), window.clicks_label.text(),
                         tuple(label.text() for label in window.diagnostic_labels.values()),
                         window.timer.isActive(), window.timer.timerId(), window.timer.interval())
            with ExitStack() as stack:
                forbid_search(stack)
                for target in ("zini_explorer.build_zini_trace", "zini_trace._build_premium_context",
                               "zini_trace._find_premium_candidates"):
                    stack.enter_context(patch(target, side_effect=AssertionError(target)))
                guards = [stack.enter_context(patch.object(controller, name)) for name in
                          ("request_trace", "go_to", "next", "previous", "begin", "receive",
                           "invalidate", "set_eligible")]
                refresh = stack.enter_context(patch.object(window, "refresh"))
                for _ in range(4):
                    window.answer_display_checkbox.click()
                    self.assertEqual(tuple(getattr(controller, field) for field in fields), before)
                    self.assertIs(controller.trace, trace)
                    self.assertIs(controller.moves, moves)
                    self.assertIs(controller._player, player)
                    self.assertEqual((player.current_index, player.revealed, player.flagged_mines),
                                     player_before)
                    self.assertEqual((window.slider.value(), window.clicks_label.text(),
                                      tuple(label.text() for label in window.diagnostic_labels.values()),
                                      window.timer.isActive(), window.timer.timerId(), window.timer.interval()),
                                     ui_before)
                for guard in guards:
                    guard.assert_not_called()
                refresh.assert_not_called()
            window.timer.stop()

    def test_prev_next_and_seek_render_current_answers_in_both_display_modes(self):
        window, controller = self.window, self.controller
        for enabled in (False, True):
            window.answer_display_checkbox.setChecked(enabled)
            window.first_button.click()
            for action, index in ((window.next_button.click, 1), (window.next_button.click, 2),
                                  (window.previous_button.click, 1),
                                  (lambda: window.slider.setValue(3), 3),
                                  (window.last_button.click, 4), (window.first_button.click, 0)):
                with self.subTest(enabled=enabled, index=index):
                    action()
                    self.assertEqual(controller.current_index, index)
                    self.assertEqual(window.clicks_label.text(), f"Clicks {controller.cumulative_clicks} / 5")
                    for coord, cell in window.cells.items():
                        state = ("flagged" if coord in controller.flagged_mines else
                                 "revealed" if coord in controller.revealed else "closed")
                        self.assertEqual(cell.state, state)
                        self.assertEqual(cell.answer_label.isHidden(), not (enabled and state == "closed"))
                        if state == "closed" and enabled:
                            self.assert_covered_answer(cell, "💣" if coord in CENTER_SNAPSHOT.mines else "1",
                                                       "#000000" if coord in CENTER_SNAPSHOT.mines else NUMBER_COLORS[1])

    def test_answer_toggle_preserves_expert_layout_details_and_manual_size(self):
        window = self.create_expert_window()
        self.show_on_screen(window, QRect(0, 0, 1920, 1080))
        for expanded in (False, True, False):
            window.details_button.setChecked(expanded)
            self.app.processEvents()
            window.resize(window.width() + 10, window.height() + 10)
            self.app.processEvents()
            before = (window.size(), window.pos(), window.scroll_area.viewport().size())
            for enabled in (False, True):
                window.answer_display_checkbox.setChecked(enabled)
                self.app.processEvents()
                self.assertEqual((window.size(), window.pos(), window.scroll_area.viewport().size()), before)
                self.assertEqual(window.details_panel.isVisible(), expanded)
                self.assertEqual(window.details_button.isChecked(), expanded)
                self.assert_expert_board_fits(window)

    def test_stale_session_hides_answers_when_toggled(self):
        self.controller.invalidate()
        for enabled in (False, True):
            self.window.answer_display_checkbox.setChecked(enabled)
            for cell in self.window.cells.values():
                self.assertEqual(cell.state, "closed")
                self.assertEqual(cell.text(), "")
                self.assertEqual(cell.answer_label.text(), "")
                self.assertTrue(cell.answer_label.isHidden())

    def test_final_board_reveals_exact_safe_cells_and_only_trajectory_flags(self):
        self.window.last_button.click()
        revealed = {coord for coord, cell in self.window.cells.items() if cell.state == "revealed"}
        flags = {coord for coord, cell in self.window.cells.items() if cell.state == "flagged"}
        self.assertEqual(revealed, set(self.window.cells) - CENTER_SNAPSHOT.mines)
        self.assertEqual(flags, self.controller.flagged_mines)
        self.assertEqual(self.window.clicks_label.text(), "Clicks 5 / 5")
        for coord in revealed:
            self.assertEqual(self.window.cells[coord].text(), "1")
            self.assertIn(NUMBER_COLORS[1], self.window.cells[coord].styleSheet())
        self.assertTrue(self.window.cells[(1, 1)].text())

    def test_header_contains_only_clicks_and_flag_wording_is_consistent(self):
        labels = [label.text() for label in self.window.findChildren(QLabel)]
        self.assertNotIn("새로 놓은 깃발", labels)
        self.assertEqual(labels.count("새로 꽂은 깃발"), 2)
        self.assertFalse(any(text.startswith("Step ") or "논리 결정 단계" in text
                             or "누적 물리 클릭 수" in text for text in labels))
        self.assertEqual(self.window.clicks_label.text(), "Clicks 0 / 5")

    def test_details_default_collapsed_update_and_toggle_without_playback_changes(self):
        window = self.window
        self.assertFalse(window.details_button.isChecked())
        self.assertEqual(window.details_button.text(), "상세 정보")
        self.assertEqual(window.details_button.arrowType(), Qt.RightArrow)
        self.assertTrue(window.details_panel.isHidden())
        window.slider.setValue(2)
        self.assertEqual(window.diagnostic_labels["action"].text(), "flag_chord")
        self.assertEqual(window.diagnostic_labels["coordinate"].text(), "(1, 0)")
        window.interval_spin.setValue(5000)
        window.play_button.click()
        before = (self.controller.current_index, self.controller.trace,
                  self.controller.revealed, self.controller.flagged_mines)
        for expanded in (True, False, True):
            window.details_button.click()
            self.assertEqual(window.details_panel.isHidden(), not expanded)
            self.assertEqual(window.details_button.arrowType(), Qt.DownArrow if expanded else Qt.RightArrow)
            self.assertEqual(window.diagnostic_labels["action"].text(), "flag_chord")
            self.assertFalse(window.diagnostic_rows["tie_count"].isHidden())
            self.assertTrue(window.timer.isActive())
            self.assertEqual((self.controller.current_index, self.controller.trace,
                              self.controller.revealed, self.controller.flagged_mines), before)
        window.close()
        reopened = self.create_window(self.controller)
        self.assertFalse(reopened.details_button.isChecked())
        self.assertTrue(reopened.details_panel.isHidden())
        self.assertEqual(reopened.diagnostic_labels["action"].text(), "flag_chord")

    def test_collapsed_fallback_details_keep_tie_row_hidden_when_expanded(self):
        window = self.create_window(ready_controller(FALLBACK_SNAPSHOT, FALLBACK_RESULT))
        window.next_button.click()
        window.details_button.click()
        self.assertFalse(window.details_panel.isHidden())
        self.assertEqual(window.diagnostic_labels["action"].text(), "fallback_click")
        self.assertTrue(window.diagnostic_rows["tie_count"].isHidden())

    def show_on_screen(self, window, geometry):
        screen = Mock()
        screen.availableGeometry.return_value = geometry
        screen_patch = patch.object(window, "screen", return_value=screen)
        screen_patch.start()
        self.addCleanup(screen_patch.stop)
        window.show()
        self.app.processEvents()
        return window

    def create_expert_window(self):
        from tests.zini_fixtures import _expert_seed1003_snapshot
        from tests.zini_v1_golden import GOLDEN
        saved = GOLDEN["deterministic/expert1003"]["expected"]
        controller = ready_controller(_expert_seed1003_snapshot(), ZiniResult(
            saved["clicks"], tuple(ZiniMove(*move) for move in saved["moves"]),
        ))
        return self.create_window(controller)

    def assert_expert_board_fits(self, window):
        self.assertEqual((window.board_container.width(), window.board_container.height()), (840, 448))
        self.assertGreaterEqual(window.scroll_area.viewport().width(), 840)
        self.assertGreaterEqual(window.scroll_area.viewport().height(), 448)
        self.assertEqual(window.scroll_area.horizontalScrollBar().maximum(), 0)
        self.assertEqual(window.scroll_area.verticalScrollBar().maximum(), 0)

    def test_expert_board_fits_initial_viewport_on_1920_by_1080_screen(self):
        window = self.create_expert_window()
        available = QRect(0, 0, 1920, 1080)
        self.show_on_screen(window, available)
        self.assertTrue(available.contains(window.frameGeometry()))
        self.assert_expert_board_fits(window)
        # Reopening an existing window must not undo a user's manual resize.
        window.resize(window.width() + 30, window.height() + 20)
        size = window.size()
        window.hide()
        window.show()
        self.assertEqual(window.size(), size)

    def test_expanding_expert_details_preserves_viewport_and_collapse_restores_size_only(self):
        for index in (0, 2):
            with self.subTest(index=index):
                window = self.create_expert_window()
                available = QRect(100, 50, 1920, 1080)
                self.show_on_screen(window, available)
                window.slider.setValue(index)
                self.app.processEvents()
                self.assert_expert_board_fits(window)
                # At the bottom of the screen, expansion must also move upward.
                window.move(available.left(), available.bottom() - window.frameGeometry().height() + 1)
                collapsed_size = window.size()
                collapsed_top = window.frameGeometry().top()
                window.interval_spin.setValue(5000)
                window.play_button.click()
                controller = window.controller
                trace = controller.trace
                before = (controller.current_index, controller.revealed, controller.flagged_mines)
                cells_before = {coord: (cell.state, cell.selected, cell.newly_revealed, cell.newly_flagged)
                                for coord, cell in window.cells.items()}
                with patch("zini_explorer.build_zini_trace", side_effect=AssertionError("rebuild")):
                    window.details_button.click()
                    self.app.processEvents()
                    self.assertTrue(window.details_panel.isVisible())
                    self.assertGreater(window.height(), collapsed_size.height())
                    self.assertEqual(window.width(), collapsed_size.width())
                    self.assertLess(window.frameGeometry().top(), collapsed_top)
                    self.assertTrue(available.contains(window.frameGeometry()))
                    self.assert_expert_board_fits(window)
                    expanded_position = window.pos()
                    window.details_button.click()
                    self.app.processEvents()
                    self.assertFalse(window.details_panel.isVisible())
                    self.assertEqual(window.size(), collapsed_size)
                    self.assertEqual(window.pos(), expanded_position)
                    self.assertTrue(available.contains(window.frameGeometry()))
                    self.assert_expert_board_fits(window)
                self.assertIs(controller.trace, trace)
                self.assertEqual((controller.current_index, controller.revealed, controller.flagged_mines), before)
                self.assertEqual({coord: (cell.state, cell.selected, cell.newly_revealed, cell.newly_flagged)
                                  for coord, cell in window.cells.items()}, cells_before)
                self.assertTrue(window.timer.isActive())
                self.assertEqual(window.timer.interval(), 5000)
                window.timer.stop()

    def test_collapse_after_auto_growth_preserves_manual_resize(self):
        for width_delta, height_delta in ((30, 0), (0, 20), (0, -20)):
            with self.subTest(width_delta=width_delta, height_delta=height_delta):
                window = self.create_expert_window()
                self.show_on_screen(window, QRect(0, 0, 1920, 1080))
                window.slider.setValue(2)
                window.interval_spin.setValue(5000)
                window.play_button.click()
                controller = window.controller
                trace = controller.trace
                before = (controller.current_index, controller.revealed, controller.flagged_mines)
                collapsed_size = window.size()
                window.details_button.click()
                self.app.processEvents()
                self.assertGreater(window.height(), collapsed_size.height())
                self.assert_expert_board_fits(window)
                window.resize(window.width() + width_delta, window.height() + height_delta)
                self.app.processEvents()
                manual_size, manual_position = window.size(), window.pos()
                window.details_button.click()
                self.app.processEvents()
                self.assertEqual(window.size(), manual_size)
                self.assertEqual(window.pos(), manual_position)
                self.assert_expert_board_fits(window)
                self.assertIs(controller.trace, trace)
                self.assertEqual((controller.current_index, controller.revealed, controller.flagged_mines), before)
                self.assertTrue(window.timer.isActive())
                window.timer.stop()

    def test_reexpansion_recalculates_from_current_size_and_screen(self):
        window = self.create_expert_window()
        available = QRect(0, 0, 1920, 1080)
        self.show_on_screen(window, available)
        initial_size = window.size()
        window.details_button.click()
        self.app.processEvents()
        self.assert_expert_board_fits(window)
        first_expanded_size = window.size()
        window.details_button.click()
        self.app.processEvents()
        self.assertEqual(window.size(), initial_size)

        # A new cycle remembers this current size, not the first cycle's size.
        window.resize(window.width() + 30, window.height() + 20)
        second_collapsed_size = window.size()
        window.details_button.click()
        self.app.processEvents()
        self.assertGreater(window.height(), second_collapsed_size.height())
        self.assertEqual(window.width(), second_collapsed_size.width())
        self.assert_expert_board_fits(window)
        window.details_button.click()
        self.app.processEvents()
        self.assertEqual(window.size(), second_collapsed_size)
        self.assert_expert_board_fits(window)

        # Less available vertical space caps the next growth and allows scrolling.
        smaller = QRect(0, 0, available.width(),
                        (second_collapsed_size.height() + first_expanded_size.height()) // 2)
        window.screen().availableGeometry.return_value = smaller
        window.details_button.click()
        self.app.processEvents()
        self.assertTrue(smaller.contains(window.frameGeometry()))
        self.assertGreater(window.scroll_area.verticalScrollBar().maximum(), 0)
        self.assertLess(window.scroll_area.viewport().height(), window.board_container.height())
        window.details_button.click()
        self.app.processEvents()
        self.assertEqual(window.size(), second_collapsed_size)
        self.assert_expert_board_fits(window)

    def test_details_toggle_and_hide_show_preserve_manual_size_when_board_already_fits(self):
        window = self.create_expert_window()
        available = QRect(0, 0, 1920, 1080)
        self.show_on_screen(window, available)
        frame_height = window.frameGeometry().height() - window.height()
        window.resize(window.width() + 30, available.height() - frame_height)
        manual_size = window.size()
        for expanded in (True, False):
            window.details_button.click()
            self.app.processEvents()
            self.assertEqual(window.details_panel.isVisible(), expanded)
            self.assertEqual(window.size(), manual_size)
            self.assert_expert_board_fits(window)
            window.hide()
            window.show()
            self.app.processEvents()
            self.assertEqual(window.size(), manual_size)
            self.assert_expert_board_fits(window)

    def test_oversized_board_uses_scroll_area_and_initial_size_stays_on_screen(self):
        width, height = 40, 24
        snapshot = BoardSnapshot(width, height, 0, True, frozenset(), ((0,) * width,) * height)
        result = ZiniResult(1, (ZiniMove("fallback_click", 0, 0, None, 1),))
        window = self.create_window(ready_controller(snapshot, result))
        available = QRect(50, 30, 640, 480)
        self.show_on_screen(window, available)
        self.assertTrue(available.contains(window.frameGeometry()))
        self.assertGreater(window.scroll_area.horizontalScrollBar().maximum(), 0)
        self.assertGreater(window.scroll_area.verticalScrollBar().maximum(), 0)
        self.assertEqual(window.board_container.width(), width * zini_explorer_ui.CELL_SIZE)
        initial_width = window.width()
        window.details_button.click()
        self.app.processEvents()
        self.assertTrue(window.details_panel.isVisible())
        self.assertTrue(available.contains(window.frameGeometry()))
        self.assertEqual(window.width(), initial_width)
        self.assertGreater(window.scroll_area.horizontalScrollBar().maximum(), 0)
        self.assertGreater(window.scroll_area.verticalScrollBar().maximum(), 0)
        self.assertLess(window.scroll_area.viewport().height(), window.board_container.height())
        expanded_size = window.size()
        window.details_button.click()
        self.app.processEvents()
        self.assertEqual(window.size(), expanded_size)

    def test_final_unflagged_mine_stays_closed_and_zero_cells_are_blank(self):
        snapshot = BoardSnapshot(3, 3, 1, True, {(0, 0)},
                                 ((0, 1, 0), (1, 1, 0), (0, 0, 0)))
        result = ZiniResult(1, (ZiniMove("fallback_click", 2, 0, None, 1),))
        controller = ready_controller(snapshot, result)
        window = self.create_window(controller)
        for enabled in (False, True):
            window.answer_display_checkbox.setChecked(enabled)
            for coord, cell in window.cells.items():
                if coord not in snapshot.mines and snapshot.adjacent[coord[1]][coord[0]] == 0:
                    self.assertEqual(cell.state, "closed")
                    self.assertEqual(cell.text(), "")
                    self.assertEqual(cell.answer_label.text(), "")
                    self.assertTrue(cell.answer_label.isHidden())
        window.last_button.click()
        self.assertEqual(controller.flagged_mines, frozenset())
        self.assertEqual(window.cells[(0, 0)].state, "closed")
        self.assertEqual(window.cells[(0, 0)].text(), "")
        self.assert_covered_answer(window.cells[(0, 0)], "💣", "#000000")
        for enabled in (False, True):
            window.answer_display_checkbox.setChecked(enabled)
            for coord in controller.revealed:
                self.assertTrue(window.cells[coord].answer_label.isHidden())
        self.assertEqual({coord for coord, cell in window.cells.items() if cell.state == "revealed"},
                         set(window.cells) - snapshot.mines)
        for (x, y), cell in window.cells.items():
            if (x, y) not in snapshot.mines:
                self.assertEqual(cell.text(), str(snapshot.adjacent[y][x]) if snapshot.adjacent[y][x] else "")

    def test_navigation_slider_and_boundary_controls(self):
        window = self.window
        self.assertFalse(window.first_button.isEnabled())
        self.assertFalse(window.previous_button.isEnabled())
        self.assertTrue(window.next_button.isEnabled())
        self.assertTrue(window.last_button.isEnabled())
        self.assertTrue(window.play_button.isEnabled())
        for action, expected in ((window.next_button.click, 1), (window.next_button.click, 2),
                                 (window.previous_button.click, 1), (window.last_button.click, 4),
                                 (window.first_button.click, 0), (lambda: window.slider.setValue(3), 3)):
            action()
            self.assertEqual(self.controller.current_index, expected)
            self.assertEqual(window.slider.value(), expected)
            self.assertEqual(window.clicks_label.text(), f"Clicks {self.controller.cumulative_clicks} / 5")
        window.last_button.click()
        self.assertTrue(window.first_button.isEnabled())
        self.assertTrue(window.previous_button.isEnabled())
        self.assertFalse(window.next_button.isEnabled())
        self.assertFalse(window.last_button.isEnabled())
        self.assertFalse(window.play_button.isEnabled())
        self.assertEqual((window.slider.minimum(), window.slider.maximum()), (0, 4))

    def slider_handle_rect(self, slider):
        option = QStyleOptionSlider()
        slider.initStyleOption(option)
        return slider.style().subControlRect(
            QStyle.CC_Slider, option, QStyle.SC_SliderHandle, slider,
        )

    def test_slider_track_clicks_jump_immediately_and_stop_autoplay_without_recalculation(self):
        window = self.create_expert_window()
        self.show_on_screen(window, QRect(0, 0, 1920, 1080))
        controller, slider = window.controller, window.slider
        trace, moves = controller.trace, controller.moves
        window.interval_spin.setValue(5000)
        with ExitStack() as stack:
            forbid_search(stack)
            for target in ("zini_explorer.build_zini_trace", "zini_trace._build_premium_context",
                           "zini_trace._find_premium_candidates"):
                stack.enter_context(patch(target, side_effect=AssertionError(target)))
            request = stack.enter_context(patch.object(controller, "request_trace"))
            go_to = stack.enter_context(patch.object(controller, "go_to", wraps=controller.go_to))
            for enabled in (False, True):
                window.answer_display_checkbox.setChecked(enabled)
                for fraction in (0.25, 0.5, 0.75):
                    with self.subTest(enabled=enabled, fraction=fraction):
                        window.first_button.click()
                        window.play_button.click()
                        self.assertTrue(window.timer.isActive())
                        go_to.reset_mock()
                        point = QPoint(round((slider.width() - 1) * fraction), slider.height() // 2)
                        QTest.mousePress(slider, Qt.LeftButton, pos=point)
                        try:
                            index = controller.current_index
                            self.assertAlmostEqual(index, round(controller.step_count * fraction), delta=1)
                            self.assertEqual(slider.value(), index)
                            go_to.assert_called_once_with(index)
                            self.assertFalse(window.timer.isActive())
                            self.assertEqual(controller.revealed, frozenset(
                                cell for step in trace.steps[:index] for cell in step.newly_revealed
                            ))
                            self.assertEqual(controller.flagged_mines, frozenset(
                                cell for step in trace.steps[:index] for cell in step.newly_flagged
                            ))
                            self.assertEqual(window.clicks_label.text(),
                                             f"Clicks {controller.cumulative_clicks} / {controller.clicks}")
                        finally:
                            QTest.mouseRelease(slider, Qt.LeftButton, pos=point)
                        window._advance_autoplay()  # A queued timeout cannot undo the seek.
                        self.assertEqual(controller.current_index, index)
                        self.assertIs(controller.trace, trace)
                        self.assertIs(controller.moves, moves)
            request.assert_not_called()

    def test_slider_track_exact_ends_seek_zero_and_step_count(self):
        for window in (self.window, self.create_expert_window()):
            self.show_on_screen(window, QRect(0, 0, 1920, 1080))
            slider, controller = window.slider, window.controller
            for x, expected in ((0, 0), (slider.width() - 1, controller.step_count)):
                with self.subTest(step_count=controller.step_count, expected=expected):
                    slider.setValue(controller.step_count // 2)
                    QTest.mouseClick(slider, Qt.LeftButton, pos=QPoint(x, slider.height() // 2))
                    self.assertEqual(slider.value(), expected)
                    self.assertEqual(controller.current_index, expected)
                    self.assertEqual(window.previous_button.isEnabled(), expected > 0)
                    self.assertEqual(window.next_button.isEnabled(), expected < controller.step_count)

    def test_slider_track_click_at_same_index_stops_autoplay(self):
        window = self.window
        self.show_on_screen(window, QRect(0, 0, 1920, 1080))
        slider = window.slider
        point = QPoint(self.slider_handle_rect(slider).right() + 1, slider.height() // 2)
        window.interval_spin.setValue(5000)
        window.play_button.click()
        self.assertTrue(window.timer.isActive())
        with patch.object(self.controller, "go_to", wraps=self.controller.go_to) as go_to:
            QTest.mouseClick(slider, Qt.LeftButton, pos=point)
        self.assertFalse(window.timer.isActive())
        self.assertEqual(slider.value(), 0)
        self.assertEqual(self.controller.current_index, 0)
        go_to.assert_not_called()

    def test_slider_handle_drag_keeps_grab_offset_and_navigation_working(self):
        window = self.window
        self.show_on_screen(window, QRect(0, 0, 1920, 1080))
        slider = window.slider
        slider.setValue(1)
        handle = self.slider_handle_rect(slider)
        press = QPoint(handle.right() - 1, handle.center().y())
        window.interval_spin.setValue(5000)
        window.play_button.click()
        QTest.mousePress(slider, Qt.LeftButton, pos=press)
        try:
            self.assertTrue(slider.isSliderDown())
            self.assertEqual(self.controller.current_index, 1)
            self.assertFalse(window.timer.isActive())
            for expected in (2, 3):
                point = press + QPoint(round((slider.width() - handle.width()) * (expected - 1) / 4), 0)
                # Explicit held-button state makes native dragging deterministic offscreen.
                event = QMouseEvent(QEvent.MouseMove, QPointF(point),
                                    QPointF(slider.mapToGlobal(point)), Qt.NoButton,
                                    Qt.LeftButton, Qt.NoModifier)
                self.app.sendEvent(slider, event)
                self.assertTrue(slider.isSliderDown())
                self.assertEqual(slider.value(), expected)
                self.assertEqual(self.controller.current_index, expected)
        finally:
            QTest.mouseRelease(slider, Qt.LeftButton, pos=press)
        self.assertFalse(slider.isSliderDown())
        for action, expected in ((window.previous_button.click, 2), (window.next_button.click, 3),
                                 (window.first_button.click, 0), (window.last_button.click, 4)):
            action()
            self.assertEqual(slider.value(), expected)
            self.assertEqual(self.controller.current_index, expected)

    def test_flag_chord_diagnostics_distinguish_logical_steps_and_physical_clicks(self):
        self.window.slider.setValue(2)
        self.assertEqual(self.controller.current_index, 2)
        self.assertEqual(self.window.clicks_label.text(), "Clicks 3 / 5")
        expected = {"action": "flag_chord", "coordinate": "(1, 0)", "premium": "2",
                    "best_premium": "2", "newly_revealed": "4", "newly_flagged": "1",
                    "tie_count": "2", "selection": "현재 상태 기준 greedy"}
        for key, value in expected.items():
            self.assertEqual(self.window.diagnostic_labels[key].text(), value, key)
        self.assertFalse(self.window.diagnostic_labels["tie_count"].isHidden())
        self.window.next_button.click()
        self.assertEqual(self.window.diagnostic_labels["coordinate"].text(), "(0, 1)")
        self.assertEqual(self.window.diagnostic_labels["premium"].text(), "1")
        self.assertEqual(self.window.diagnostic_labels["newly_flagged"].text(), "0")

    def test_all_selection_wording_is_explicitly_state_relative(self):
        expected = {
            ZiniTraceSelection.GREEDY: "현재 상태 기준 greedy",
            ZiniTraceSelection.MAX_TIE_ALT: "현재 상태 기준 최대 Premium 동률",
            ZiniTraceSelection.BELOW_MAX: "현재 상태 기준 최대 Premium 미만",
            ZiniTraceSelection.FALLBACK_GREEDY: "현재 상태 기준 첫 fallback",
            ZiniTraceSelection.FALLBACK_ALT: "현재 상태 기준 다른 fallback",
        }
        self.assertEqual(zini_explorer_ui.SELECTION_TEXT, expected)
        variants = (
            (CENTER_SNAPSHOT, ZiniResult(5, (
                ZiniMove("click", 0, 1, 2, 1), ZiniMove("flag_chord", 0, 1, 2, 2),
                ZiniMove("flag_chord", 1, 0, 1, 1), ZiniMove("flag_chord", 2, 1, 0, 1),
            )), ZiniTraceSelection.MAX_TIE_ALT),
            (CENTER_SNAPSHOT, ZiniResult(5, (
                ZiniMove("click", 0, 0, 0, 1), ZiniMove("click", 2, 1, 2, 1),
                ZiniMove("flag_chord", 2, 1, 2, 2), ZiniMove("flag_chord", 1, 2, 1, 1),
            )), ZiniTraceSelection.BELOW_MAX),
            (FALLBACK_SNAPSHOT, FALLBACK_RESULT, ZiniTraceSelection.FALLBACK_ALT),
        )
        for snapshot, result, selection in variants:
            with self.subTest(selection=selection):
                controller = ready_controller(snapshot, result)
                window = self.create_window(controller)
                window.next_button.click()
                self.assertEqual(controller.current_step.selection, selection)
                self.assertEqual(window.diagnostic_labels["selection"].text(), expected[selection])

    def test_fallback_hides_number_candidate_ties_at_both_fallback_positions(self):
        controller = ready_controller(FALLBACK_SNAPSHOT, FALLBACK_RESULT)
        window = self.create_window(controller)
        for expected in ("현재 상태 기준 다른 fallback", "현재 상태 기준 첫 fallback"):
            window.next_button.click()
            self.assertEqual(controller.current_step.tie_count, 2)
            self.assertEqual(window.diagnostic_labels["action"].text(), "fallback_click")
            self.assertEqual(window.diagnostic_labels["premium"].text(), "—")
            self.assertEqual(window.diagnostic_labels["best_premium"].text(), "-2")
            self.assertEqual(window.diagnostic_labels["selection"].text(), expected)
            self.assertTrue(window.diagnostic_rows["tie_count"].isHidden())
            self.assertTrue(window.diagnostic_labels["tie_count"].isHidden())

    def test_selected_and_delta_highlights_match_step_and_clear_at_zero(self):
        for index in (1, 2, 3, 0):
            self.window.slider.setValue(index)
            step = self.controller.current_step
            before = (self.controller.revealed, self.controller.flagged_mines)
            self.window.refresh()
            self.assertEqual((self.controller.revealed, self.controller.flagged_mines), before)
            for coord, cell in self.window.cells.items():
                self.assertEqual(cell.selected, bool(step and coord == (step.move.x, step.move.y)))
                self.assertEqual(cell.newly_revealed, bool(step and coord in step.newly_revealed))
                self.assertEqual(cell.newly_flagged, bool(step and coord in step.newly_flagged))
                if index == 2 and coord == (1, 1):
                    self.assertEqual(cell.state, "flagged")
                    self.assertTrue(cell.text())
        self.assertTrue(self.window.diagnostic_rows["tie_count"].isHidden())

    def test_real_qtimer_advances_one_logical_step_per_timeout_and_stops(self):
        observed = []
        self.window.interval_spin.setValue(20)
        self.window.timer.timeout.connect(lambda: observed.append(self.controller.current_index))
        self.window.play_button.click()
        deadline = time.monotonic() + 3
        while self.window.timer.isActive() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertFalse(self.window.timer.isActive())
        self.assertEqual(observed, [1, 2, 3, 4])
        self.assertEqual(self.controller.current_index, 4)
        self.assertEqual(self.window.clicks_label.text(), "Clicks 5 / 5")
        self.assertFalse(self.window.play_button.isEnabled())

    def test_manual_navigation_and_slider_stop_autoplay(self):
        self.window.interval_spin.setValue(5000)
        for name, action in (
            ("first", self.window.first_button.click),
            ("previous", self.window.previous_button.click),
            ("next", self.window.next_button.click),
            ("last", self.window.last_button.click),
            ("slider", lambda: self.window.slider.setValue(1)),
        ):
            with self.subTest(action=name):
                self.window.slider.setValue(2)
                self.window.play_button.click()
                self.assertTrue(self.window.timer.isActive())
                action()
                self.assertFalse(self.window.timer.isActive())
                before = self.controller.current_index
                self.window._advance_autoplay()  # A queued timeout cannot resume playback.
                self.assertEqual(self.controller.current_index, before)

    def test_play_pause_and_interval_change_update_active_timer(self):
        self.assertEqual(self.window.interval_spin.value(), 200)
        self.assertEqual((self.window.interval_spin.minimum(), self.window.interval_spin.maximum()),
                         (20, 5000))
        self.window.play_button.click()
        self.assertTrue(self.window.timer.isActive())
        self.window.interval_spin.setValue(350)
        self.assertEqual(self.window.timer.interval(), 350)
        self.assertTrue(self.window.timer.isActive())
        self.window.play_button.click()
        self.assertFalse(self.window.timer.isActive())

    def test_auxiliary_close_preserves_cache_and_reopen_preserves_position(self):
        trace = self.controller.trace
        self.window.slider.setValue(2)
        self.window.play_button.click()
        self.window.close()
        self.assertFalse(self.window.timer.isActive())
        self.assertIs(self.controller.trace, trace)
        self.assertEqual(self.controller.current_index, 2)
        with patch("zini_explorer.build_zini_trace", side_effect=AssertionError("rebuild")):
            reopened = self.create_window(self.controller)
        self.assertEqual(reopened.slider.value(), 2)
        self.assertEqual(reopened.clicks_label.text(), "Clicks 3 / 5")
        self.assertFalse(reopened.timer.isActive())

    def test_empty_trace_has_no_enabled_navigation_and_mine_stays_covered(self):
        controller = ready_controller(BoardSnapshot(1, 1, 1, True, {(0, 0)}, ((0,),)), ZiniResult(0))
        window = self.create_window(controller)
        self.assertEqual((controller.current_index, controller.step_count), (0, 0))
        self.assertEqual(window.clicks_label.text(), "Clicks 0 / 0")
        for control in (window.first_button, window.previous_button, window.play_button,
                        window.next_button, window.last_button, window.slider):
            self.assertFalse(control.isEnabled())
        self.assertEqual(window.cells[(0, 0)].state, "closed")


@unittest.skipIf(QApplication is None, "PyQt5 unavailable")
class ExplorerMainUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.engine = MinesweeperEngine(3, 3, 1)
        self.settings = isolate_ui_settings(self)
        self.ui = MinesweeperUI(self.engine)
        self.addCleanup(self.close_ui)
        warning = patch("ui_manager.QMessageBox.warning")
        self.warning = warning.start()
        self.addCleanup(warning.stop)

    def close_ui(self):
        self.ui.close()
        self.ui.deleteLater()
        self.app.processEvents()

    def launch(self):
        process = Mock()
        process.poll.return_value = None
        with patch("ui_manager.subprocess.Popen", return_value=process) as popen:
            self.ui._ensure_zini_metric_job()
        popen.assert_called_once()
        return process

    def prepare_live(self, status=GameStatus.LOST, *, pending=False, **changes):
        self.ui._reset_zini_metric_job()
        self.engine.reset_with_mines(3, 3, 1, {(1, 1)})
        if status == GameStatus.LOST:
            self.engine.step(1, 1, Action.OPEN)
        elif status == GameStatus.WON:
            for x, y in sorted(set((x, y) for y in range(3) for x in range(3)) - {(1, 1)}):
                self.engine.step(x, y, Action.OPEN)
        self.assertEqual(self.engine.status, status)
        self.launch()
        if not pending:
            self.finish(**changes)

    def finish(self, **changes):
        result = payload(self.ui._zini_job_token, **changes)
        write_result_atomic(self.ui._zini_result_path, result)
        self.ui._poll_zini_metric_job()
        return result

    def replay(self, outcome):
        cells = ([(0, 0)] if outcome == "pending" else
                 [(0, 0), (1, 1)] if outcome == "lost" else
                 [(x, y) for y in range(3) for x in range(3) if (x, y) != (1, 1)])
        return ReplayPlayer(ReplayData(
            ReplayBoard(3, 3, 1, {(1, 1)}),
            tuple(ReplayEvent(float(i + 1), x, y, ACTION_OPEN) for i, (x, y) in enumerate(cells)),
        ))

    def enter_replay(self, outcome):
        player = self.replay(outcome)
        process = Mock()
        process.poll.return_value = None
        with patch("ui_manager.subprocess.Popen", return_value=process):
            self.ui._enter_replay_mode(player)
        return player

    def assert_invalidated(self):
        self.assertIsNone(self.ui._zini_explorer_window)
        self.assertFalse(self.ui.zini_explorer_button.isEnabled())
        controller = self.ui._zini_explorer
        for field in ("token", "snapshot", "moves", "trace", "current_index"):
            self.assertIsNone(getattr(controller, field), field)
        with patch("ui_manager.subprocess.Popen", side_effect=AssertionError("stale search")):
            self.ui.on_open_zini_explorer()
        self.assertIsNone(self.ui._zini_explorer_window)

    def test_live_playing_and_pending_are_disabled_and_answer_data_stays_hidden(self):
        self.assertFalse(self.ui.zini_explorer_button.isEnabled())
        self.prepare_live(GameStatus.PLAYING, pending=True)
        self.assertFalse(self.ui.zini_explorer_button.isEnabled())
        self.finish()
        with patch("zini_explorer.build_zini_trace") as build:
            self.ui.on_open_zini_explorer()
        build.assert_not_called()
        self.assertFalse(self.ui.zini_explorer_button.isEnabled())
        self.assertIsNone(self.ui._zini_explorer_window)
        self.assertIsNone(self.ui._zini_explorer.snapshot)
        self.assertIsNone(self.ui._zini_explorer.moves)
        self.prepare_live(pending=True)
        self.assertFalse(self.ui.zini_explorer_button.isEnabled())

    def test_live_won_lost_results_enable_entry_without_building_trace_for_counters(self):
        for status in (GameStatus.WON, GameStatus.LOST):
            with self.subTest(status=status), patch("zini_explorer.build_zini_trace", wraps=build_zini_trace) as build:
                self.prepare_live(status)
                self.ui._counter_metric_values()
                self.ui._update_statistics_panel(self.engine.get_stats())
                self.assertTrue(self.ui.zini_explorer_button.isEnabled())
                build.assert_not_called()
                self.ui.zini_explorer_button.click()
                build.assert_called_once()
                self.assertIsNotNone(self.ui._zini_explorer_window)

    def test_open_is_explicit_lazy_boundary_and_repeated_activation_reuses_one_window(self):
        self.prepare_live()
        before = (self.engine.get_observation(), self.engine.get_counter_snapshot())
        with ExitStack() as stack:
            forbid_search(stack)
            stack.enter_context(patch.object(self.engine, "step", side_effect=AssertionError("game mutation")))
            stack.enter_context(patch.object(self.engine, "get_board_snapshot", side_effect=AssertionError("engine rendering")))
            request = stack.enter_context(patch.object(
                self.ui, "request_zini_explorer_trace", wraps=self.ui.request_zini_explorer_trace,
            ))
            build = stack.enter_context(patch("zini_explorer.build_zini_trace", wraps=build_zini_trace))
            self.ui.zini_explorer_button.click()
            window = self.ui._zini_explorer_window
            self.assertTrue(window.isWindow())
            self.assertTrue(window.isVisible())
            window.slider.setValue(2)
            self.ui.zini_explorer_button.click()
            self.assertIs(self.ui._zini_explorer_window, window)
            trace = self.ui._zini_explorer.trace
            window.close()
            self.assertIsNone(self.ui._zini_explorer_window)
            self.assertIs(self.ui._zini_explorer.trace, trace)
            self.ui.zini_explorer_button.click()
            reopened = self.ui._zini_explorer_window
            self.assertIsNot(reopened, window)
            self.assertIs(self.ui._zini_explorer.trace, trace)
            self.assertEqual(reopened.slider.value(), 2)
            self.assertEqual(reopened.clicks_label.text(), "Clicks 3 / 5")
            self.assertEqual(request.call_count, 3)
            build.assert_called_once()
        self.assertEqual((self.engine.get_observation(), self.engine.get_counter_snapshot()), before)

    def test_eligibility_revocation_closes_window_without_exposing_cached_state(self):
        self.prepare_live()
        with patch("zini_explorer.build_zini_trace", wraps=build_zini_trace) as build:
            self.ui.on_open_zini_explorer()
            trace = self.ui._zini_explorer.trace
            window = self.ui._zini_explorer_window
            window.slider.setValue(2)
            window.play_button.click()
            self.engine.status = GameStatus.PLAYING
            self.ui._update_statistics_panel(self.engine.get_stats())
            self.assertFalse(window.isVisible())
            self.assertFalse(window.timer.isActive())
            self.assertIsNone(self.ui._zini_explorer_window)
            self.assertFalse(self.ui.zini_explorer_button.isEnabled())
            self.assertIsNone(self.ui._zini_explorer.trace)
            self.assertIsNone(self.ui._zini_explorer.snapshot)
            self.ui.on_open_zini_explorer()
            self.assertIsNone(self.ui._zini_explorer_window)
            self.engine.status = GameStatus.LOST
            self.ui._update_statistics_panel(self.engine.get_stats())
            self.ui.on_open_zini_explorer()
            self.assertIs(self.ui._zini_explorer.trace, trace)
            self.assertEqual(self.ui._zini_explorer.current_index, 2)
            build.assert_called_once()

    def test_successful_worker_cleanup_does_not_close_completed_explorer(self):
        self.prepare_live(pending=True)
        paths = (self.ui._zini_payload_path, self.ui._zini_result_path)
        original_finish = self.ui._finish_zini_metric_process
        opened = []

        def finish_after_open():
            self.ui.on_open_zini_explorer()
            opened.append(self.ui._zini_explorer_window)
            original_finish()

        with patch.object(self.ui, "_finish_zini_metric_process", side_effect=finish_after_open):
            self.finish()
        self.assertIsNotNone(opened[0])
        self.assertIs(self.ui._zini_explorer_window, opened[0])
        self.assertTrue(opened[0].isVisible())
        self.assertIsNotNone(self.ui._zini_explorer.trace)
        self.assertEqual(self.ui._current_zini_clicks(), 5)
        self.assertIsNone(self.ui._zini_process)
        self.assertFalse(any(Path(path).exists() for path in paths))

    def test_worker_transport_and_lazy_trace_errors_disable_entry_preserving_valid_clicks(self):
        cases = (
            {"clicks": None, "moves": None, "error": "worker failed"},
            {"moves": None},
            {"moves": (replace(CENTER_RESULT.moves[0], premium=99), *CENTER_RESULT.moves[1:])},
        )
        for changes in cases:
            with self.subTest(changes=changes):
                self.prepare_live(**changes)
                if self.ui._zini_explorer.error is None:
                    self.assertTrue(self.ui.zini_explorer_button.isEnabled())
                self.ui.on_open_zini_explorer()
                self.assertIsNotNone(self.ui._zini_explorer.error)
                self.assertFalse(self.ui.zini_explorer_button.isEnabled())
                self.assertIsNone(self.ui._zini_explorer_window)
                expected = changes.get("clicks", 5)
                self.assertEqual(self.ui._current_zini_clicks(), expected)
                if expected is not None:
                    self.assertEqual(self.ui._stat_value_items["zini"].text(), "5")

    def test_trace_builder_exception_disables_entry_without_search_or_counter_loss(self):
        self.prepare_live()
        with ExitStack() as stack:
            forbid_search(stack)
            build = stack.enter_context(patch("zini_explorer.build_zini_trace", side_effect=RuntimeError("failed")))
            self.ui.on_open_zini_explorer()
            self.ui.on_open_zini_explorer()
        build.assert_called_once()
        self.assertFalse(self.ui.zini_explorer_button.isEnabled())
        self.assertIsNone(self.ui._zini_explorer_window)
        self.assertEqual(self.ui._current_zini_clicks(), 5)
        self.assertEqual(self.ui._stat_value_items["zini"].text(), "5")

    def test_reset_board_change_and_main_close_close_window_and_reject_old_result(self):
        for action in (self.ui.on_reset, lambda: self.ui._rebuild_game(4, 3, 1), self.ui.close):
            with self.subTest(action=action):
                self.prepare_live()
                self.ui.on_open_zini_explorer()
                window = self.ui._zini_explorer_window
                window.play_button.click()
                old_token = self.ui._zini_job_token
                action()
                self.assertFalse(window.isVisible())
                self.assertFalse(window.timer.isActive())
                self.assert_invalidated()
                self.assertFalse(self.ui._zini_explorer.receive(payload(old_token), expected_token=old_token))
                self.assert_invalidated()

    def test_replay_entry_exit_close_old_window_and_invalidate_old_session(self):
        self.prepare_live()
        self.ui.on_open_zini_explorer()
        live_window = self.ui._zini_explorer_window
        old_token = self.ui._zini_job_token
        self.enter_replay("lost")
        self.assertFalse(live_window.isVisible())
        self.assertIsNone(self.ui._zini_explorer_window)
        self.assertNotEqual(self.ui._zini_explorer.token, old_token)
        self.assertFalse(self.ui._zini_explorer.receive(payload(old_token), expected_token=old_token))
        self.finish()
        self.ui.on_open_zini_explorer()
        replay_window = self.ui._zini_explorer_window
        self.assertIsNotNone(replay_window)
        self.ui._exit_replay_mode()
        self.assertFalse(replay_window.isVisible())
        self.assert_invalidated()

    def test_incomplete_replay_blocks_entry_even_with_delivered_result(self):
        player = self.enter_replay("pending")
        self.launch()
        self.finish()
        with patch("zini_explorer.build_zini_trace") as build:
            for index in (0, player.event_count):
                player.go_to(index)
                self.ui._refresh_replay_view_after_move()
                self.assertFalse(self.ui.zini_explorer_button.isEnabled())
                self.ui.on_open_zini_explorer()
                self.assertIsNone(self.ui._zini_explorer_window)
                self.assertIsNone(self.ui._zini_explorer.snapshot)
        build.assert_not_called()

    def test_completed_replay_enables_entry_at_first_middle_final_for_won_and_lost(self):
        for outcome in ("won", "lost"):
            with self.subTest(outcome=outcome):
                player = self.enter_replay(outcome)
                self.finish()
                with patch("zini_explorer.build_zini_trace", wraps=build_zini_trace) as build:
                    for index in (0, player.event_count // 2, player.event_count):
                        player.go_to(index)
                        self.ui._refresh_replay_view_after_move()
                        self.assertTrue(self.ui.zini_explorer_button.isEnabled())
                        self.ui.zini_explorer_button.click()
                        self.assertIsNotNone(self.ui._zini_explorer_window)
                        self.assertEqual(player.current_index, index)
                    build.assert_called_once()
                self.ui._exit_replay_mode()
                self.assert_invalidated()


if __name__ == "__main__":
    unittest.main()
