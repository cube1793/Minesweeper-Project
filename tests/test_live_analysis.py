"""Stage 2-4A: pure presentation plus real offscreen Qt lifecycle regressions."""

import os
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from core_engine import Action, CellState, GameStatus, MinesweeperEngine
from live_analysis import (
    CellOverlay, OverlayKind, first_click_presentation, format_mine_probability,
    is_all_hidden, present_decision, reduced_number,
)
from simple_algorithm import InconsistentObservationError, InferenceResult, SimpleMove
from simple_decision import DecisionKind, SimpleDecision, analyze_position
from simple_probability import CellProbability, ProbabilityResult

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PyQt5.QtWidgets import QApplication
except ImportError:
    QApplication = None
else:
    from ui_manager import MinesweeperUI

H, F = CellState.HIDDEN, CellState.FLAGGED


def probability_decision(counts, denominator, move, kind=DecisionKind.PROBABILITY_GUESS):
    result = ProbabilityResult(
        denominator,
        tuple(CellProbability(coordinate, count, denominator)
              for coordinate, count in counts.items()),
        (), tuple(counts),
    )
    return SimpleDecision(kind, move, (), InferenceResult((), ()), result)


class LiveAnalysisPresentationTests(unittest.TestCase):
    def test_first_click_has_only_recommendation_without_safe_or_probability(self):
        result = first_click_presentation()
        self.assertEqual(result.status_text, "첫 클릭 추천: OPEN (0, 0)")
        self.assertEqual(result.move, SimpleMove(Action.OPEN, 0, 0))
        self.assertEqual(set(result.overlays), {(0, 0)})
        self.assertTrue(result.overlays[(0, 0)].recommended)
        self.assertIsNone(result.overlays[(0, 0)].kind)
        self.assertIsNone(result.overlays[(0, 0)].probability)
        self.assertTrue(is_all_hidden([[H, H], [H, H]]))
        for observation in ([], [[]], [[H], []], [[H, F]], [[0, H]]):
            self.assertFalse(is_all_hidden(observation))

    def test_local_evidence_is_preserved_without_probability_calls(self):
        observation = [[0, H, H, 3], [H, H, H, H]]
        before = deepcopy(observation)
        with (
            patch("simple_decision.calculate_probabilities") as calculate,
            patch("simple_probability.calculate_probabilities") as calculate_core,
        ):
            decision = analyze_position(observation, 3)
            result = present_decision(observation, decision)
        calculate.assert_not_called()
        calculate_core.assert_not_called()
        self.assertIs(result.decision, decision)
        self.assertEqual(result.move, decision.move)
        self.assertEqual(self.cells_of_kind(result, OverlayKind.SAFE), {(1, 0), (0, 1), (1, 1)})
        self.assertEqual(self.cells_of_kind(result, OverlayKind.MINE), {(2, 0), (2, 1), (3, 1)})
        self.assertEqual(self.recommended_cells(result), {(2, 0)})
        self.assertEqual(result.status_text, "확정 안전 3칸, 확정 지뢰 3칸 | 추천: FLAG (2, 0)")
        self.assertTrue(all(cell.probability is None for cell in result.overlays.values()))
        self.assertEqual(observation, before)

    def test_guess_ties_use_exact_minimum_and_trust_non_reading_order_move(self):
        denominator = 10**400
        decision = probability_decision(
            {(0, 0): 1, (2, 0): 1, (3, 0): 2, (4, 0): 0, (5, 0): 0},
            denominator, SimpleMove(Action.OPEN, 2, 0),
        )
        result = present_decision([[H, 1, H, H, F, 0]], decision)
        self.assertEqual(self.cells_of_kind(result, OverlayKind.GUESS_CANDIDATE), {(0, 0), (2, 0)})
        self.assertEqual(self.cells_of_kind(result, OverlayKind.UNCERTAIN), {(3, 0)})
        self.assertEqual(self.recommended_cells(result), {(2, 0)})
        self.assertEqual(set(result.overlays), {(0, 0), (2, 0), (3, 0)})
        for cell in decision.probability_result.probabilities[:3]:
            self.assertIs(result.overlays[cell.coordinate].probability, cell)

    def test_global_certainties_and_near_endpoints_remain_distinct(self):
        denominator = 10**400
        decision = probability_decision(
            {(0, 0): 0, (1, 0): denominator, (2, 0): 1, (3, 0): denominator - 1},
            denominator, SimpleMove(Action.FLAG, 1, 0), DecisionKind.GLOBAL_CERTAINTY,
        )
        result = present_decision([[H, H, H, H]], decision)
        self.assertEqual(self.cells_of_kind(result, OverlayKind.SAFE), {(0, 0)})
        self.assertEqual(self.cells_of_kind(result, OverlayKind.MINE), {(1, 0)})
        self.assertEqual(self.cells_of_kind(result, OverlayKind.UNCERTAIN), {(2, 0), (3, 0)})
        self.assertEqual(self.recommended_cells(result), {(1, 0)})
        self.assertEqual(
            [format_mine_probability(cell.probability, compact=True) for cell in result.overlays.values()],
            ["0%", "100%", "<1%", ">99%"],
        )
        self.assertEqual(result.status_text, "확정 안전 1칸, 확정 지뢰 1칸 | 추천: FLAG (1, 0)")

    def test_compact_percent_format_boundaries_and_rounding(self):
        for numerator, denominator, expected in (
            (0, 1, "0%"), (1, 1, "100%"), (1, 101, "<1%"),
            (1, 100, "1%"), (99, 100, "99%"), (100, 101, ">99%"),
            (1, 10**400, "<1%"), (10**400 - 1, 10**400, ">99%"),
            (17, 93, "18%"), (1, 3, "33%"), (2, 3, "67%"),
            (2049, 10000, "20%"), (205, 1000, "21%"), (9899, 10000, "99%"),
        ):
            with self.subTest(numerator=numerator, denominator=denominator):
                self.assertEqual(
                    format_mine_probability(CellProbability((0, 0), numerator, denominator), compact=True),
                    expected,
                )

    def test_detail_percent_uses_one_decimal_without_rounding_to_certainty(self):
        for numerator, denominator, expected in (
            (0, 1, "0%"), (1, 1, "100%"), (1, 10**400, "<0.1%"),
            (10**400 - 1, 10**400, ">99.9%"), (1, 1000, "0.1%"),
            (999, 1000, "99.9%"), (17, 93, "18.3%"), (206, 1000, "20.6%"),
        ):
            with self.subTest(numerator=numerator, denominator=denominator):
                self.assertEqual(
                    format_mine_probability(CellProbability((0, 0), numerator, denominator)), expected,
                )

    def test_status_keeps_existing_move_and_short_probability_without_world_counts(self):
        denominator = 10**400
        decision = probability_decision(
            {(1, 0): 206 * (denominator // 1000)}, denominator, SimpleMove(Action.OPEN, 1, 0),
        )
        result = present_decision([[1, H]], decision)
        self.assertEqual(result.status_text, "추천: OPEN (1, 0) | 지뢰 확률 20.6%")
        self.assertIs(result.decision, decision)
        self.assertIs(result.overlays[(1, 0)].probability, decision.probability_result.probabilities[0])

    def test_no_decision_has_no_overlay(self):
        result = present_decision([[1, F]], None)
        self.assertIsNone(result.move)
        self.assertEqual(result.overlays, {})

    def test_reduction_counts_adjacent_flags_only_without_mutation(self):
        observation = [[F, F, H, F], [F, 1, H, F], [H, H, F, F]]
        before = deepcopy(observation)
        self.assertEqual(reduced_number(observation, 1, 1), -3)
        self.assertEqual(observation, before)

    @staticmethod
    def cells_of_kind(result, kind):
        return {coordinate for coordinate, overlay in result.overlays.items() if overlay.kind == kind}

    @staticmethod
    def recommended_cells(result):
        return {coordinate for coordinate, overlay in result.overlays.items() if overlay.recommended}


@unittest.skipIf(QApplication is None, "PyQt5 unavailable; pure presentation tests still run")
class LiveAnalysisUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        # ZiNi subprocess launch is unrelated; all live/replay/UI behavior is real.
        worker_patch = patch.object(MinesweeperUI, "_ensure_zini_metric_job")
        worker_patch.start()
        self.addCleanup(worker_patch.stop)
        self.engine = MinesweeperEngine(3, 3, 1)
        self.ui = MinesweeperUI(self.engine)
        self.addCleanup(self.close_ui)

    def close_ui(self):
        self.ui._stop_timer()
        self.ui._stop_replay_autoplay()
        self.ui.close()
        self.ui.deleteLater()
        self.app.processEvents()

    def prepared_board(self):
        self.engine.reset_with_mines(3, 3, 1, {(1, 1)})
        self.engine.step(0, 0, Action.OPEN)
        self.ui.render_board()

    def assert_clear(self):
        self.assertIsNone(self.ui._analysis_result)
        self.assertTrue(all(btn.analysis_overlay is None for btn in self.ui._buttons.values()))
        self.assertTrue(all(btn.probability_text == "" for btn in self.ui._buttons.values()))
        self.assertTrue(all(btn.toolTip() == "" for btn in self.ui._buttons.values()))

    def test_defaults_and_manual_first_click_do_not_call_solver_or_step(self):
        self.assertFalse(self.ui.analysis_checkbox.isChecked())
        self.assertTrue(self.ui.probability_checkbox.isChecked())
        self.assertFalse(self.ui.reduction_checkbox.isChecked())
        with (
            patch("ui_manager.analyze_position") as analyze,
            patch("simple_decision.calculate_probabilities") as calculate,
            patch("simple_probability.calculate_probabilities") as calculate_core,
            patch.object(self.engine, "step") as step,
        ):
            self.ui.analyze_button.click()
            self.assertIn("첫 클릭 추천", self.ui.analysis_status_label.text())
            self.assertEqual(self.ui._analysis_result.move, SimpleMove(Action.OPEN, 0, 0))
            self.assertTrue(self.ui._buttons[(0, 0)].analysis_overlay.recommended)
            self.assertTrue(all(not btn.probability_text for btn in self.ui._buttons.values()))
            self.ui.analysis_checkbox.setChecked(True)
        analyze.assert_not_called()
        calculate.assert_not_called()
        calculate_core.assert_not_called()
        step.assert_not_called()

    def test_local_ui_does_not_request_probabilities(self):
        self.prepared_board()
        self.engine.step(1, 1, Action.FLAG)
        self.ui.render_board()
        with (
            patch("simple_decision.calculate_probabilities") as calculate,
            patch("simple_probability.calculate_probabilities") as calculate_core,
            patch.object(self.engine, "step") as step,
        ):
            self.ui.analyze_button.click()
            self.ui.probability_checkbox.setChecked(False)
            self.ui.probability_checkbox.setChecked(True)
        calculate.assert_not_called()
        calculate_core.assert_not_called()
        step.assert_not_called()
        result = self.ui._analysis_result
        self.assertEqual(result.decision.kind, DecisionKind.LOCAL_DETERMINISTIC)
        self.assertIsNone(result.decision.probability_result)
        self.assertEqual(result.move, result.decision.move)
        self.assertTrue(all(not btn.probability_text for btn in self.ui._buttons.values()))
        self.assertEqual(self.ui._buttons[(1, 0)].analysis_overlay.kind, OverlayKind.SAFE)

    def test_flag_then_unflag_all_hidden_uses_normal_analysis_manual_and_live(self):
        for automatic in (False, True):
            with self.subTest(automatic=automatic):
                self.ui.on_reset()
                self.ui.analysis_checkbox.setChecked(automatic)
                self.assertFalse(self.engine.get_board_snapshot().mines_placed)
                with patch("core_engine.random.sample", return_value=[(0, 0)]):
                    self.ui.on_right_click(1, 1)
                self.assertTrue(self.engine.get_board_snapshot().mines_placed)

                with (
                    patch("ui_manager.analyze_position", wraps=analyze_position) as analyze,
                    patch.object(self.engine, "step", wraps=self.engine.step) as step,
                ):
                    self.ui.on_right_click(1, 1)
                    if not automatic:
                        self.ui.analyze_button.click()

                observation = self.engine.get_observation()
                self.assertTrue(is_all_hidden(observation))
                self.assertTrue(self.engine.get_board_snapshot().mines_placed)
                self.assertNotIn("첫 클릭 추천", self.ui.analysis_status_label.text())
                self.assertNotIn("안전", self.ui.analysis_status_label.text())
                analyze.assert_called_once_with(observation, self.engine.num_mines)
                step.assert_called_once_with(1, 1, Action.FLAG)
                self.assertEqual(self.ui._analysis_result.decision.kind, DecisionKind.PROBABILITY_GUESS)
                origin = self.ui._buttons[(0, 0)]
                self.assertEqual(origin.analysis_overlay.kind, OverlayKind.GUESS_CANDIDATE)
                self.assertEqual(origin.probability_text, "11%")

    def test_first_click_policy_uses_only_snapshot_placement_boolean(self):
        for placed in (False, True):
            with self.subTest(placed=placed):
                self.engine.reset()
                if placed:
                    self.engine.step(1, 1, Action.FLAG)
                    self.engine.step(1, 1, Action.FLAG)
                observation = self.engine.get_observation()
                # Access to hidden layout fields would fail on this snapshot.
                with (
                    patch.object(self.engine, "get_board_snapshot",
                                 return_value=SimpleNamespace(mines_placed=placed)) as snapshot,
                    patch("ui_manager.analyze_position", wraps=analyze_position) as analyze,
                    patch.object(self.engine, "step") as step,
                ):
                    self.ui.analyze_button.click()
                snapshot.assert_called_once_with()
                step.assert_not_called()
                if placed:
                    analyze.assert_called_once_with(observation, self.engine.num_mines)
                    self.assertEqual(self.ui._analysis_result.decision.kind, DecisionKind.PROBABILITY_GUESS)
                else:
                    analyze.assert_not_called()
                    self.assertIn("첫 클릭 추천", self.ui.analysis_status_label.text())

    def test_probability_toggle_reuses_result_and_preserves_button_state(self):
        self.engine.reset_with_mines(3, 3, 1, {(2, 2)})
        self.engine.step(1, 1, Action.OPEN)
        self.ui.render_board()
        base = {pos: (btn.text(), btn.styleSheet()) for pos, btn in self.ui._buttons.items()}
        with patch("ui_manager.analyze_position", wraps=analyze_position) as analyze:
            self.ui.analyze_button.click()
            result = self.ui._analysis_result
            self.assertEqual(result.decision.kind, DecisionKind.PROBABILITY_GUESS)
            self.assertTrue(self.ui._buttons[(1, 0)].probability_text)
            self.ui.probability_checkbox.setChecked(False)
            self.assertTrue(all(not btn.probability_text for btn in self.ui._buttons.values()))
            self.assertIs(self.ui._analysis_result, result)
            self.ui.probability_checkbox.setChecked(True)
            self.ui.on_cell_size_changed(10)
            self.assertEqual(analyze.call_count, 1)
        # Restoring the size must restore exactly the same base text/style.
        self.ui.on_cell_size_changed(28)
        self.assertEqual(base, {pos: (btn.text(), btn.styleSheet()) for pos, btn in self.ui._buttons.items()})

    def test_manual_result_clears_on_open_flag_and_both_chord(self):
        for handler, coordinate in (
            (self.ui.on_left_click, (1, 0)),
            (self.ui.on_right_click, (1, 1)),
            (self.ui.on_both_click, (0, 0)),
            (self.ui.on_left_click, (0, 0)),
        ):
            with self.subTest(handler=handler.__name__, coordinate=coordinate):
                self.prepared_board()
                if coordinate == (0, 0):
                    self.engine.step(1, 1, Action.FLAG)
                    self.ui.render_board()
                self.ui.analyze_button.click()
                self.assertIsNotNone(self.ui._analysis_result)
                before = self.engine.get_observation()
                with patch("ui_manager.analyze_position") as analyze:
                    handler(*coordinate)
                self.assertNotEqual(self.engine.get_observation(), before)
                analyze.assert_not_called()
                self.assert_clear()

    def test_live_on_invalidates_then_renders_then_analyzes_fresh_after_every_action(self):
        self.prepared_board()
        self.ui.analysis_checkbox.setChecked(True)
        for handler, coordinate in (
            (self.ui.on_right_click, (1, 1)),
            (self.ui.on_left_click, (1, 0)),
            (self.ui.on_both_click, (0, 0)),
        ):
            with self.subTest(handler=handler.__name__):
                before = self.engine.get_observation()
                rendered = []
                render = self.ui.render_board

                def check_render():
                    self.assert_clear()
                    render()
                    rendered.append(self.engine.get_observation())

                def check_analyze(observation, mines):
                    self.assert_clear()
                    self.assertEqual(observation, self.engine.get_observation())
                    self.assertNotEqual(observation, before)
                    self.assertEqual(rendered[-1], observation)
                    for y, row in enumerate(observation):
                        for x, value in enumerate(row):
                            if 1 <= value <= 8:
                                self.assertEqual(self.ui._buttons[(x, y)].text(), str(value))
                    return analyze_position(observation, mines)

                with (
                    patch.object(self.ui, "render_board", side_effect=check_render),
                    patch("ui_manager.analyze_position", side_effect=check_analyze) as analyze,
                    patch.object(self.engine, "step", wraps=self.engine.step) as step,
                ):
                    handler(*coordinate)
                self.assertEqual(step.call_count, 1)
                self.assertEqual(analyze.call_count, 1)
                self.assertIsNotNone(self.ui._analysis_result)

    def test_off_toggle_clears_and_stops_automatic_analysis(self):
        self.prepared_board()
        self.ui.analysis_checkbox.setChecked(True)
        self.ui.analysis_checkbox.setChecked(False)
        self.assert_clear()
        with patch("ui_manager.analyze_position") as analyze:
            self.ui.on_right_click(1, 1)
        analyze.assert_not_called()
        self.assert_clear()

    def test_reset_and_difficulty_clear_manual_and_refresh_live_results(self):
        for enabled in (False, True):
            self.ui.analysis_checkbox.setChecked(enabled)
            for reset in (self.ui.on_reset, lambda: self.ui.on_difficulty_changed("초급 (9x9, 10)")):
                self.ui.analyze_button.click()
                old = self.ui._analysis_result
                with patch("ui_manager.analyze_position") as analyze:
                    reset()
                analyze.assert_not_called()
                if enabled:
                    self.assertIsNot(self.ui._analysis_result, old)
                    self.assertIn("첫 클릭 추천", self.ui.analysis_status_label.text())
                else:
                    self.assert_clear()

    def test_won_and_lost_clear_without_analyzing_terminal_observation(self):
        for terminal in (GameStatus.WON, GameStatus.LOST):
            with self.subTest(status=terminal):
                self.ui.on_reset()
                self.prepared_board()
                if terminal == GameStatus.WON:
                    for y in range(3):
                        for x in range(3):
                            if (x, y) not in ((1, 1), (2, 2)):
                                self.engine.step(x, y, Action.OPEN)
                    self.ui.render_board()
                self.ui.analysis_checkbox.setChecked(True)
                self.ui.analyze_button.click()
                with patch("ui_manager.analyze_position") as analyze:
                    self.ui.on_left_click(*( (2, 2) if terminal == GameStatus.WON else (1, 1) ))
                    self.ui.analyze_button.click()
                self.assertEqual(self.engine.status, terminal)
                analyze.assert_not_called()
                self.assertIn("게임 종료", self.ui.analysis_status_label.text())
                self.assert_clear()

    def test_reduction_changes_only_display_and_solver_sees_original_observation(self):
        for mines, flags, original_text, reduced_text in (
            ({(1, 1)}, ((1, 1),), "1", ""),
            ({(1, 0), (1, 1)}, ((1, 1),), "2", "1"),
            ({(1, 1)}, ((1, 0), (0, 1), (1, 1)), "1", "-2"),
        ):
            with self.subTest(original=original_text, reduced=reduced_text):
                self.engine.reset_with_mines(3, 3, len(mines), mines)
                self.engine.step(0, 0, Action.OPEN)
                for coordinate in flags:
                    self.engine.step(*coordinate, Action.FLAG)
                self.ui.render_board()
                before = self.engine.get_observation()
                snapshot = self.engine.get_board_snapshot()
                counters = self.engine.get_counter_snapshot()
                button = self.ui._buttons[(0, 0)]
                original_style = button.styleSheet()
                self.assertFalse(self.ui.reduction_checkbox.isChecked())
                self.assertEqual(button.text(), original_text)

                with patch.object(self.engine, "step") as step:
                    self.ui.reduction_checkbox.setChecked(True)
                    self.assertEqual(button.text(), reduced_text)
                    self.assertEqual(button.styleSheet(), original_style)
                    self.assertEqual(self.engine.get_observation(), before)
                    with patch("ui_manager.analyze_position", wraps=analyze_position) as analyze:
                        self.ui.analyze_button.click()
                    analyze.assert_called_once_with(before, len(mines))
                    self.assertEqual(self.engine.get_observation(), before)
                    self.ui.reduction_checkbox.setChecked(False)
                    self.assertEqual(button.text(), original_text)
                step.assert_not_called()
                self.assertEqual(self.engine.get_observation(), before)
                self.assertEqual(self.engine.get_board_snapshot(), snapshot)
                self.assertEqual(self.engine.get_counter_snapshot(), counters)

    def test_invalid_public_state_clears_previous_result_without_engine_changes(self):
        self.prepared_board()
        self.ui.analyze_button.click()
        # Two flags contradict the opened 1 and the public total mine count.
        self.engine.step(1, 0, Action.FLAG)
        self.engine.step(0, 1, Action.FLAG)
        before = self.engine.get_observation()
        counters = self.engine.get_counter_snapshot()
        with patch.object(self.engine, "step") as step:
            self.ui.analyze_button.click()
        step.assert_not_called()
        self.assertIn("분석 불가 - 공개 상태가 모순됩니다.", self.ui.analysis_status_label.text())
        self.assert_clear()
        self.assertEqual(self.engine.get_observation(), before)
        self.assertEqual(self.engine.get_counter_snapshot(), counters)

    def test_other_solver_errors_are_contained_and_clear_existing_overlay(self):
        self.prepared_board()
        for error in (ValueError("invalid input"), TypeError("invalid type"), RuntimeError("solver failed")):
            self.ui.analyze_button.click()
            with (
                patch("ui_manager.analyze_position", side_effect=error),
                patch.object(self.engine, "step") as step,
            ):
                self.ui.analyze_button.click()
            self.assertIn("분석 불가", self.ui.analysis_status_label.text())
            self.assert_clear()
            step.assert_not_called()

    def test_failed_live_analysis_adds_no_extra_action(self):
        self.prepared_board()
        self.ui.analysis_checkbox.setChecked(True)
        with (
            patch("ui_manager.analyze_position", side_effect=InconsistentObservationError("bad flags")),
            patch.object(self.engine, "step", wraps=self.engine.step) as step,
        ):
            self.ui.on_right_click(1, 1)
        step.assert_called_once_with(1, 1, Action.FLAG)
        self.assert_clear()
        self.assertIn("분석 불가", self.ui.analysis_status_label.text())

    def test_replay_reuses_analysis_controls_and_live_controls_work_after_exit(self):
        from replay_model import ACTION_CHORD, ACTION_FLAG, ACTION_OPEN, ReplayBoard, ReplayData, ReplayEvent
        from replay_player import ReplayPlayer

        self.prepared_board()
        self.ui.analysis_checkbox.setChecked(True)
        self.ui.reduction_checkbox.setChecked(True)
        before = self.engine.get_observation()
        player = ReplayPlayer(ReplayData(
            ReplayBoard(3, 3, 1, {(1, 1)}),
            (ReplayEvent(1.0, 0, 0, ACTION_OPEN),
             ReplayEvent(2.0, 1, 1, ACTION_FLAG),
             ReplayEvent(3.0, 0, 0, ACTION_CHORD)),
        ))
        controls = (self.ui.analysis_checkbox, self.ui.probability_checkbox,
                    self.ui.reduction_checkbox, self.ui.analyze_button)
        with patch("ui_manager.analyze_position") as analyze:
            self.ui._enter_replay_mode(player)
            self.assertIn("첫 클릭 추천", self.ui.analysis_status_label.text())
            self.assertTrue(all(control.isEnabled() for control in controls))
            self.ui.on_analyze_current()
            self.ui.analyze_button.click()
            self.ui.on_replay_next()
            self.ui.on_replay_next()
            self.assertEqual(self.ui._buttons[(0, 0)].text(), "")
            self.ui.on_replay_last()
            self.assertEqual(player.current_index, 3)
            self.ui.on_replay_previous()
            self.ui.on_replay_first()
            self.assertEqual(player.current_index, 0)
            self.assertEqual(self.engine.get_observation(), before)
            self.assertIn("첫 클릭 추천", self.ui.analysis_status_label.text())
            self.ui.on_exit_replay()
            self.assertIs(self.ui.engine, self.engine)
            self.assertTrue(all(control.isEnabled() for control in controls))
            self.assertIn("첫 클릭 추천", self.ui.analysis_status_label.text())
        analyze.assert_not_called()
        self.ui.analysis_checkbox.setChecked(False)
        self.ui.on_right_click(1, 1)
        self.ui.analyze_button.click()
        self.assertIsNotNone(self.ui._analysis_result)

    def test_overlay_paints_at_supported_cell_sizes_without_changing_base_state(self):
        self.prepared_board()
        denominator = 10**400
        decision = probability_decision(
            {(1, 0): 1, (2, 0): denominator - 1, (0, 1): 0, (1, 1): denominator},
            denominator, SimpleMove(Action.OPEN, 1, 0),
        )
        with patch("ui_manager.analyze_position", return_value=decision):
            self.ui.analyze_button.click()
        for size in (10, 28, 60):
            with self.subTest(size=size):
                self.ui.on_cell_size_changed(size)
                self.ui.show()
                self.app.processEvents()
                for coordinate in decision.probability_result.unconstrained_cells:
                    button = self.ui._buttons[coordinate]
                    self.assertFalse(button.grab().isNull())
                    self.assertEqual(button.text(), "")
                self.assertEqual(self.ui._buttons[(1, 0)].probability_text, "<1%")
                self.assertEqual(self.ui._buttons[(2, 0)].probability_text, ">99%")

    def test_tooltips_are_short_and_do_not_show_raw_world_counts(self):
        denominator = 10**400
        button = self.ui._buttons[(0, 0)]
        for kind, numerator, expected_text, expected_tip in (
            (OverlayKind.SAFE, 0, "0%", "안전 확정"),
            (OverlayKind.MINE, denominator, "100%", "지뢰 확정"),
            (OverlayKind.UNCERTAIN, 206 * (denominator // 1000), "21%", "지뢰 확률: 20.6%"),
            (OverlayKind.GUESS_CANDIDATE, 1, "<1%", "지뢰 확률: <0.1%"),
            (OverlayKind.UNCERTAIN, denominator - 1, ">99%", "지뢰 확률: >99.9%"),
        ):
            for recommended in (False, True):
                with self.subTest(kind=kind, recommended=recommended):
                    probability = CellProbability((0, 0), numerator, denominator)
                    overlay = CellOverlay(kind, recommended, probability)
                    button.set_analysis_overlay(overlay)
                    tooltip = ("추천 셀 · " if recommended else "") + expected_tip
                    self.assertEqual(button.toolTip(), tooltip)
                    self.assertEqual(button.probability_text, expected_text)
                    self.assertIs(button.analysis_overlay.probability, probability)
                    button.set_analysis_overlay(overlay, show_probability=False)
                    self.assertEqual(button.toolTip(), tooltip)
                    self.assertEqual(button.probability_text, "")
        for kind, expected in ((OverlayKind.SAFE, "안전 확정"), (OverlayKind.MINE, "지뢰 확정")):
            button.set_analysis_overlay(CellOverlay(kind))
            self.assertEqual(button.toolTip(), expected)
            self.assertEqual(button.probability_text, "")

    def test_initial_expert_window_fits_board_without_internal_scrollbars(self):
        self.ui.close()
        self.ui.deleteLater()
        self.ui = MinesweeperUI(MinesweeperEngine(30, 16, 99))
        self.ui.show()
        self.app.processEvents()
        for analyze in (False, True):
            if analyze:
                self.ui.analyze_button.click()
                self.app.processEvents()
            viewport = self.ui.scroll_area.viewport()
            self.assertGreaterEqual(viewport.width(), 30 * 28)
            self.assertGreaterEqual(viewport.height(), 16 * 28)
            self.assertEqual(self.ui.scroll_area.horizontalScrollBar().maximum(), 0)
            self.assertEqual(self.ui.scroll_area.verticalScrollBar().maximum(), 0)
        self.assertLessEqual(self.ui.width(), 1500)
        self.assertLessEqual(self.ui.height(), 900)

    def test_large_board_initial_window_keeps_existing_size_limits(self):
        with (
            patch.object(self.ui, "_engine_for_current_mode", return_value=SimpleNamespace(width=100, height=100)),
            patch.object(self.ui, "resize") as resize,
        ):
            self.ui._apply_initial_window_size()
        resize.assert_called_once_with(1500, 900)


if __name__ == "__main__":
    unittest.main()
