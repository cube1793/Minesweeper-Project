"""Stage 2-5 real Qt controls, replay navigation and read-only solver boundary."""

import os
import unittest
from copy import deepcopy
from unittest.mock import patch

from core_engine import Action, CellState, GameStatus, MinesweeperEngine
from replay_analysis import analyze_replay_step
from replay_model import ReplayBoard, ReplayData, ReplayEvent
from replay_player import ReplayPlayer
from simple_decision import analyze_position

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PyQt5.QtWidgets import QApplication
except ImportError:
    QApplication = None
else:
    from ui_manager import MinesweeperUI, REPLAY_MODE_TIME


def replay_data():
    # OPEN -> FLAG -> UNFLAG -> other OPEN; remains PLAYING at the final index.
    return ReplayData(ReplayBoard(3, 3, 1, {(1, 1)}), (
        ReplayEvent(1.0, 0, 0, "OPEN"), ReplayEvent(2.0, 1, 1, "FLAG"),
        ReplayEvent(3.0, 1, 1, "FLAG"), ReplayEvent(4.0, 2, 0, "OPEN"),
    ))


@unittest.skipIf(QApplication is None, "PyQt5 unavailable")
class ReplayAnalysisUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        worker_patch = patch.object(MinesweeperUI, "_ensure_zini_metric_job")
        worker_patch.start()
        self.addCleanup(worker_patch.stop)
        self.engine = MinesweeperEngine(3, 3, 1)
        self.ui = MinesweeperUI(self.engine)
        self.addCleanup(self.close_ui)
        self.player = ReplayPlayer(replay_data())

    def close_ui(self):
        self.ui._stop_replay_autoplay()
        self.ui._stop_timer()
        self.ui.close()
        self.ui.deleteLater()
        self.app.processEvents()

    def enter(self, index=0, continuous=False):
        self.player.go_to(index)
        self.ui._enter_replay_mode(self.player)
        self.ui.analysis_checkbox.setChecked(continuous)

    def assert_clear(self):
        self.assertIsNone(self.ui._analysis_result)
        self.assertIsNone(self.ui._replay_analysis_result)
        for button in self.ui._buttons.values():
            self.assertIsNone(button.analysis_overlay)
            self.assertEqual(button.probability_text, "")
            self.assertEqual(button.toolTip(), "")

    def assert_auto_off(self):
        self.assertFalse(self.ui._simple_auto_timer.isActive())
        self.assertFalse(self.ui._simple_auto_pending)
        for control in (self.ui.simple_auto_checkbox, self.ui.allow_guess_checkbox):
            self.assertFalse(control.isChecked())
            self.assertFalse(control.isEnabled())

    def test_replay_enables_analysis_controls_and_cancels_pending_auto(self):
        self.ui.simple_auto_checkbox.setChecked(True)
        self.ui.allow_guess_checkbox.setChecked(True)
        self.assertTrue(self.ui._simple_auto_timer.isActive())
        self.ui._enter_replay_mode(self.player)
        for control in (self.ui.analysis_checkbox, self.ui.probability_checkbox,
                        self.ui.reduction_checkbox, self.ui.analyze_button):
            self.assertTrue(control.isEnabled())
        self.assert_auto_off()
        with patch.object(self.engine, "step") as live_step, patch.object(self.player.engine, "step") as replay_step:
            self.ui.simple_auto_checkbox.setChecked(True)
            self.ui.allow_guess_checkbox.setChecked(True)
            self.ui._on_simple_auto_timeout()
            self.ui.analyze_button.click()
            self.ui._on_simple_auto_timeout()
        self.assert_auto_off()
        live_step.assert_not_called()
        replay_step.assert_not_called()

    def test_manual_analysis_is_read_only_and_clears_on_navigation(self):
        self.enter(1)
        engine = self.player.engine
        timeline = self.ui._replay_counter_timeline
        before = deepcopy((engine.get_observation(), engine.get_counter_snapshot(),
                           self.engine.get_observation(), self.engine.get_counter_snapshot(),
                           self.player.replay_data, timeline))
        with (
            patch.object(engine, "step") as replay_step,
            patch.object(self.engine, "step") as live_step,
            patch.object(engine, "get_board_snapshot", side_effect=AssertionError("snapshot")),
            patch.object(self.engine, "get_board_snapshot", side_effect=AssertionError("live snapshot")),
            patch.object(ReplayBoard, "mine_positions", create=True,
                         new=property(lambda _: self.fail("hidden layout"))),
            patch("replay_analysis.analyze_position", wraps=analyze_position) as analyze,
        ):
            for _ in range(3):
                self.ui.analyze_button.click()
            self.assertEqual(analyze.call_count, 3)
            self.assertIsNotNone(self.ui._analysis_result)
            self.assertIn("실제 다음 수: FLAG (1, 1)", self.ui.analysis_status_label.text())
        replay_step.assert_not_called()
        live_step.assert_not_called()
        self.assertIs(self.player.engine, engine)
        self.assertIs(self.ui.engine, self.engine)
        self.assertIs(self.ui._replay_counter_timeline, timeline)
        self.assertEqual(self.player.current_index, 1)
        self.assertEqual((engine.get_observation(), engine.get_counter_snapshot(),
                          self.engine.get_observation(), self.engine.get_counter_snapshot(),
                          self.player.replay_data, timeline), before)
        with patch("ui_manager.analyze_replay_step") as analyze:
            self.ui.replay_next_button.click()
            analyze.assert_not_called()
        self.assert_clear()

    def test_first_click_uses_index_without_snapshot_even_when_mines_placed(self):
        self.enter()
        self.assertTrue(self.player.engine.get_board_snapshot().mines_placed)
        with (
            patch.object(self.player.engine, "get_board_snapshot", side_effect=AssertionError("snapshot")),
            patch("replay_analysis.analyze_position") as analyze,
        ):
            self.ui.analysis_checkbox.setChecked(True)
        analyze.assert_not_called()
        self.assertIn("첫 클릭 추천: OPEN (0, 0)", self.ui.analysis_status_label.text())
        self.assertIn("추천과 일치", self.ui.analysis_status_label.text())

    def test_continuous_navigation_analyzes_fresh_after_render_exactly_once(self):
        self.enter(continuous=True)
        original_render = self.ui.render_board
        rendered = []

        def render():
            self.assert_clear()
            original_render()
            rendered.append(self.player.current_index)

        def analyze(observation, num_mines, **kwargs):
            self.assertEqual(rendered[-1], self.player.current_index)
            self.assertEqual(observation, self.player.get_observation())
            self.assertEqual(kwargs["current_index"], self.player.current_index)
            return analyze_replay_step(observation, num_mines, **kwargs)

        transitions = ((self.ui.replay_next_button.click, 1),
                       (self.ui.replay_next_button.click, 2),
                       (self.ui.replay_prev_button.click, 1),
                       (self.ui.replay_last_button.click, 4),
                       (self.ui.replay_first_button.click, 0),
                       (lambda: self.ui.replay_slider.setValue(3), 3))
        with patch.object(self.ui, "render_board", side_effect=render), patch(
            "ui_manager.analyze_replay_step", side_effect=analyze,
        ) as analysis:
            for transition, expected in transitions:
                with self.subTest(index=expected):
                    before = analysis.call_count
                    transition()
                    self.assertEqual(self.player.current_index, expected)
                    self.assertEqual(analysis.call_count, before + 1)
                    result = self.ui._replay_analysis_result
                    self.assertEqual(result.current_index, expected)
                    self.assertIs(result.next_event, self.player.replay_data.events[expected]
                                  if expected < 4 else None)
                    self.assert_auto_off()

    def test_analysis_off_clears_and_manual_can_resume_without_continuous(self):
        self.enter(1, continuous=True)
        self.ui.analysis_checkbox.setChecked(False)
        self.assert_clear()
        with patch("ui_manager.analyze_replay_step", wraps=analyze_replay_step) as analyze:
            self.ui.replay_next_button.click()
            analyze.assert_not_called()
            self.ui.analyze_button.click()
            self.assertEqual(analyze.call_count, 1)
            self.ui.replay_prev_button.click()
            self.assertEqual(analyze.call_count, 1)
        self.assert_clear()

    def test_index_autoplay_refreshes_analysis_once_per_tick(self):
        self.enter(continuous=True)
        self.ui.replay_play_button.click()
        with patch("ui_manager.analyze_replay_step", wraps=analyze_replay_step) as analyze:
            for expected in range(1, 5):
                self.ui._advance_replay_autoplay()
                self.assertEqual(analyze.call_count, expected)
                self.assertEqual(self.ui._replay_analysis_result.current_index, expected)
        self.assertFalse(self.ui._replay_autoplay_timer.isActive())
        self.assertIn("다음 실제 수 없음", self.ui.analysis_status_label.text())
        self.assert_auto_off()

    def test_time_autoplay_batches_due_events_and_skips_idle_ticks(self):
        self.enter(continuous=True)
        self.ui.replay_playback_mode_combo.setCurrentText(REPLAY_MODE_TIME)
        with patch("ui_manager.time.perf_counter", return_value=100):
            self.ui.replay_play_button.click()
        with patch("replay_analysis.analyze_position", wraps=analyze_position) as solve, patch(
            "ui_manager.analyze_replay_step", wraps=analyze_replay_step,
        ) as analyze:
            with patch("ui_manager.time.perf_counter", return_value=102.5):
                self.ui._advance_replay_autoplay()
            self.assertEqual(self.player.current_index, 2)
            self.assertEqual(analyze.call_count, 1)
            solve.assert_called_once_with(self.player.get_observation(), 1)
            for wall_time in (102.6, 102.7):
                with patch("ui_manager.time.perf_counter", return_value=wall_time):
                    self.ui._advance_replay_autoplay()
            self.assertEqual(analyze.call_count, 1)
            self.assertEqual(solve.call_count, 1)
            with patch("ui_manager.time.perf_counter", return_value=104.5):
                self.ui._advance_replay_autoplay()
            self.assertEqual(self.player.current_index, 4)
            self.assertEqual(analyze.call_count, 2)
        self.assert_auto_off()

    def test_time_seek_same_index_and_slider_sync_reuse_current_analysis(self):
        self.enter(1, continuous=True)
        self.ui.replay_playback_mode_combo.setCurrentText(REPLAY_MODE_TIME)
        result = self.ui._replay_analysis_result
        with patch("ui_manager.analyze_replay_step", wraps=analyze_replay_step) as analyze:
            self.ui.replay_slider.setValue(1500)
            self.ui._sync_replay_slider()
            self.ui._refresh_replay_view_after_move()
            analyze.assert_not_called()
            self.assertIs(self.ui._replay_analysis_result, result)
            self.ui.replay_slider.setValue(2500)
            self.assertEqual(analyze.call_count, 1)
            self.assertEqual(self.ui._replay_analysis_result.current_index, 2)

    def test_probability_toggle_reuses_result_and_has_no_actual_action_overlay(self):
        self.enter(3, continuous=True)
        result = self.ui._analysis_result
        step_result = self.ui._replay_analysis_result
        with patch("replay_analysis.analyze_position") as analyze:
            self.ui.probability_checkbox.setChecked(False)
            self.assertTrue(all(button.probability_text == "" for button in self.ui._buttons.values()))
            self.ui.probability_checkbox.setChecked(True)
        analyze.assert_not_called()
        self.assertIs(self.ui._analysis_result, result)
        self.assertIs(self.ui._replay_analysis_result, step_result)
        self.assertTrue(any(button.probability_text for button in self.ui._buttons.values()))
        for coordinate, button in self.ui._buttons.items():
            self.assertEqual(button.analysis_overlay, result.overlays.get(coordinate))

    def test_reduction_only_changes_display_and_solver_receives_original(self):
        self.player = ReplayPlayer(ReplayData(ReplayBoard(3, 3, 1, {(1, 1)}), (
            ReplayEvent(1, 0, 0, "OPEN"), ReplayEvent(2, 1, 1, "FLAG"),
            ReplayEvent(3, 1, 0, "FLAG"),
        )))
        self.enter(1)
        self.ui.reduction_checkbox.setChecked(True)
        self.assertEqual(self.ui._buttons[(0, 0)].text(), "1")
        self.ui.replay_next_button.click()
        self.assertEqual(self.ui._buttons[(0, 0)].text(), "")
        observation = self.player.get_observation()
        with patch("replay_analysis.analyze_position", wraps=analyze_position) as analyze:
            self.ui.analyze_button.click()
            analyze.assert_called_once_with(observation, 1)
            result = self.ui._analysis_result
            self.ui.reduction_checkbox.setChecked(False)
            self.assertEqual(self.ui._buttons[(0, 0)].text(), "1")
            self.ui.reduction_checkbox.setChecked(True)
            self.assertIs(self.ui._analysis_result, result)
            self.assertEqual(analyze.call_count, 1)
        self.ui.replay_next_button.click()
        self.assertEqual(self.ui._buttons[(0, 0)].text(), "-1")
        self.assertEqual(self.player.get_observation()[0][0], 1)

    def test_terminal_and_trailing_events_do_not_call_solver(self):
        for x, status in ((0, GameStatus.WON), (1, GameStatus.LOST)):
            with self.subTest(status=status):
                self.ui.analysis_checkbox.setChecked(False)
                self.player = ReplayPlayer(ReplayData(ReplayBoard(2, 1, 1, {(1, 0)}), (
                    ReplayEvent(1, x, 0, "OPEN"), ReplayEvent(2, 1, 0, "FLAG"),
                )))
                self.enter(continuous=True)
                with patch("replay_analysis.analyze_position") as analyze:
                    self.ui.replay_next_button.click()
                    self.assertEqual(self.player.engine.status, status)
                    self.assert_clear()
                    self.ui.analyze_button.click()
                    self.ui.replay_last_button.click()
                analyze.assert_not_called()
                self.assertEqual(self.player.current_index, 2)
                self.assertEqual(self.ui.analysis_status_label.text(), "게임 종료")
                self.assert_clear()
                self.assert_auto_off()

    def test_inconsistent_flags_do_not_stop_playback_and_next_index_recovers(self):
        self.player = ReplayPlayer(ReplayData(ReplayBoard(3, 3, 1, {(1, 1)}), (
            ReplayEvent(1, 0, 0, "OPEN"), ReplayEvent(2, 1, 1, "FLAG"),
            ReplayEvent(3, 1, 0, "FLAG"), ReplayEvent(4, 1, 0, "FLAG"),
            ReplayEvent(5, 2, 0, "OPEN"),
        )))
        self.enter(2, continuous=True)
        self.ui.replay_play_button.click()
        self.ui._advance_replay_autoplay()
        self.assertEqual(self.player.current_index, 3)
        self.assert_clear()
        self.assertIn("분석 불가 - 공개 상태가 모순됩니다.", self.ui.analysis_status_label.text())
        self.assertTrue(self.ui._replay_autoplay_timer.isActive())
        self.ui._advance_replay_autoplay()
        self.assertEqual(self.player.current_index, 4)
        self.assertIsNotNone(self.ui._analysis_result)
        self.assertTrue(self.ui._replay_autoplay_timer.isActive())

    def test_runtime_validation_errors_stay_inside_slots_and_next_index_recovers(self):
        for error in (ValueError("invalid"), TypeError("invalid"), RuntimeError("failed")):
            with self.subTest(error=error):
                self.enter(1, continuous=True)
                with patch("replay_analysis.analyze_position", side_effect=error), patch.object(
                    self.player.engine, "step",
                ) as step:
                    self.ui.analyze_button.click()
                step.assert_not_called()
                self.assertEqual(self.player.current_index, 1)
                self.assert_clear()
                self.assertIn("분석 불가", self.ui.analysis_status_label.text())
                self.ui.replay_next_button.click()
                self.assertIsNotNone(self.ui._analysis_result)

    def test_exit_restores_live_identity_controls_and_fresh_start_without_auto(self):
        self.enter(2, continuous=True)
        self.ui.exit_replay_button.click()
        self.assertIs(self.ui.engine, self.engine)
        self.assertIsNone(self.ui._replay_analysis_result)
        self.assertFalse(self.ui._replay_mode)
        self.assertTrue(self.ui.simple_auto_checkbox.isEnabled())
        self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
        self.assertFalse(self.ui.allow_guess_checkbox.isChecked())
        self.assertFalse(self.ui._simple_auto_timer.isActive())
        self.assertFalse(self.engine.get_board_snapshot().mines_placed)
        self.assertIn("첫 클릭 추천", self.ui.analysis_status_label.text())


if __name__ == "__main__":
    unittest.main()
