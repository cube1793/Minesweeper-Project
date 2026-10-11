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
from unittest.mock import Mock, patch

# Bootstrap precedes every PyQt import as well as QApplication construction.
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from qt_bootstrap import configure_qt_plugin_path

configure_qt_plugin_path()
try:
    from PyQt5.QtCore import Qt
    from PyQt5.QtTest import QTest
    from PyQt5.QtWidgets import QApplication, QScrollArea
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
        self.assertEqual(self.window.step_label.text(), "Step 0 / 4")
        self.assertEqual(self.window.clicks_label.text(), "Clicks 0 / 5")
        for cell in self.window.cells.values():
            self.assertEqual(cell.state, "closed")
            self.assertEqual(cell.text(), "")
            self.assertFalse(cell.selected or cell.newly_revealed or cell.newly_flagged)
        for key, label in self.window.diagnostic_labels.items():
            if key != "tie_count":
                self.assertEqual(label.text(), "—", key)

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

    def test_final_unflagged_mine_stays_closed_and_zero_cells_are_blank(self):
        snapshot = BoardSnapshot(3, 3, 1, True, {(0, 0)},
                                 ((0, 1, 0), (1, 1, 0), (0, 0, 0)))
        result = ZiniResult(1, (ZiniMove("fallback_click", 2, 0, None, 1),))
        controller = ready_controller(snapshot, result)
        window = self.create_window(controller)
        window.last_button.click()
        self.assertEqual(controller.flagged_mines, frozenset())
        self.assertEqual(window.cells[(0, 0)].state, "closed")
        self.assertEqual(window.cells[(0, 0)].text(), "")
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
            self.assertEqual(window.step_label.text(), f"Step {expected} / 4")
        window.last_button.click()
        self.assertTrue(window.first_button.isEnabled())
        self.assertTrue(window.previous_button.isEnabled())
        self.assertFalse(window.next_button.isEnabled())
        self.assertFalse(window.last_button.isEnabled())
        self.assertFalse(window.play_button.isEnabled())
        self.assertEqual((window.slider.minimum(), window.slider.maximum()), (0, 4))

    def test_flag_chord_diagnostics_distinguish_logical_steps_and_physical_clicks(self):
        self.window.slider.setValue(2)
        self.assertEqual(self.window.step_label.text(), "Step 2 / 4")
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
        self.assertEqual(reopened.step_label.text(), "Step 2 / 4")
        self.assertEqual(reopened.clicks_label.text(), "Clicks 3 / 5")
        self.assertFalse(reopened.timer.isActive())

    def test_empty_trace_has_no_enabled_navigation_or_hidden_mine_disclosure(self):
        controller = ready_controller(BoardSnapshot(1, 1, 1, True, {(0, 0)}, ((0,),)), ZiniResult(0))
        window = self.create_window(controller)
        self.assertEqual(window.step_label.text(), "Step 0 / 0")
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
            self.assertEqual(reopened.step_label.text(), "Step 2 / 4")
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
