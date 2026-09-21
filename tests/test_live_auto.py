"""Stage 2-4B: real Qt controls, engine and recorder; deterministic timeouts."""

import os
import unittest
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import call, patch

from core_engine import Action, CellState, GameStatus, MinesweeperEngine
from replay_model import ReplayBoard, ReplayData, ReplayEvent
from replay_player import ReplayPlayer
from simple_algorithm import InconsistentObservationError, InferenceResult, SimpleMove
from simple_decision import DecisionKind, SimpleDecision, analyze_position
from simple_probability import CellProbability, ProbabilityResult

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PyQt5.QtWidgets import QApplication, QMessageBox
except ImportError:
    QApplication = None
else:
    from ui_manager import MinesweeperUI, SIMPLE_AUTO_STEP_INTERVAL_MS


def recommendation(action, x, y, kind=DecisionKind.LOCAL_DETERMINISTIC):
    move = SimpleMove(action, x, y)
    safe = {(x, y)} if action == Action.OPEN else set()
    mines = {(x, y)} if action == Action.FLAG else set()
    probability = None
    if kind in (DecisionKind.GLOBAL_CERTAINTY, DecisionKind.PROBABILITY_GUESS):
        count = 1 if kind == DecisionKind.PROBABILITY_GUESS else (2 if mines else 0)
        probability = ProbabilityResult(
            2, (CellProbability((x, y), count, 2),), (), ((x, y),),
        )
    return SimpleDecision(kind, move, (), InferenceResult(safe, mines), probability)


@unittest.skipIf(QApplication is None, "PyQt5 unavailable")
class LiveAutoUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        worker = patch.object(MinesweeperUI, "_ensure_zini_metric_job")
        worker.start()
        self.addCleanup(worker.stop)
        self.engine = MinesweeperEngine(3, 3, 1)
        self.ui = MinesweeperUI(self.engine)
        self.addCleanup(self.close_ui)

    def close_ui(self):
        self.ui._stop_timer()
        self.ui._stop_replay_autoplay()
        self.ui.close()
        self.ui.deleteLater()
        self.app.processEvents()

    def prepare_board(self):
        self.engine.reset_with_mines(3, 3, 1, {(1, 1)})
        self.ui.on_left_click(0, 0)

    def tick(self):
        # No sleeps or wall-clock races: deliver the connected timeout directly.
        self.ui._simple_auto_timer.timeout.emit()

    def assert_stopped(self):
        self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
        self.assertFalse(self.ui.allow_guess_checkbox.isChecked())
        self.assertFalse(self.ui.allow_guess_checkbox.isEnabled())
        self.assertFalse(self.ui._simple_auto_timer.isActive())
        self.assertFalse(self.ui._simple_auto_pending)

    def assert_clear(self):
        self.assertIsNone(self.ui._analysis_result)
        self.assertTrue(all(button.analysis_overlay is None
                            for button in self.ui._buttons.values()))

    def test_controls_defaults_enable_analysis_and_cancel_pending(self):
        self.assert_stopped()
        self.assertTrue(self.ui.simple_auto_checkbox.isEnabled())
        self.assertTrue(self.ui._simple_auto_timer.isSingleShot())
        self.assertEqual(self.ui._simple_auto_timer.interval(), SIMPLE_AUTO_STEP_INTERVAL_MS)
        self.assertFalse(self.ui.analysis_checkbox.isChecked())
        self.ui.simple_auto_checkbox.setChecked(True)
        self.assertTrue(self.ui.analysis_checkbox.isChecked())
        self.assertTrue(self.ui.allow_guess_checkbox.isEnabled())
        self.assertTrue(self.ui._simple_auto_timer.isActive())
        self.ui.allow_guess_checkbox.setChecked(True)
        with patch.object(self.engine, "step") as step:
            self.ui.simple_auto_checkbox.setChecked(False)
            self.tick()
        step.assert_not_called()
        self.assert_stopped()
        self.assertTrue(self.ui.analysis_checkbox.isChecked())
        self.assertIsNotNone(self.ui._analysis_result)

    def test_analysis_off_also_stops_auto_and_clears_overlay(self):
        self.ui.simple_auto_checkbox.setChecked(True)
        self.ui.allow_guess_checkbox.setChecked(True)
        with patch.object(self.engine, "step") as step:
            self.ui.analysis_checkbox.setChecked(False)
            self.tick()
        step.assert_not_called()
        self.assert_stopped()
        self.assert_clear()

    def test_enabling_auto_on_existing_analysis_analyzes_once(self):
        self.prepare_board()
        self.ui.analysis_checkbox.setChecked(True)
        with patch("ui_manager.analyze_position", wraps=analyze_position) as analyze:
            self.ui.simple_auto_checkbox.setChecked(True)
        analyze.assert_called_once_with(self.engine.get_observation(), 1)

    def test_first_click_skips_analyzer_then_records_once_and_analyzes_fresh(self):
        recorder = self.ui._replay_recorder
        before = self.engine.get_observation()
        observations = []

        def analyze_fresh(observation, mines):
            self.assertNotEqual(observation, before)
            self.assertEqual(observation, self.engine.get_observation())
            self.assertEqual(len(recorder.events), 1)
            observations.append(observation)
            return analyze_position(observation, mines)

        with (
            patch("core_engine.random.sample", return_value=[(1, 1)]),
            patch("ui_manager.analyze_position", side_effect=analyze_fresh) as analyze,
            patch.object(self.engine, "step", wraps=self.engine.step) as step,
            patch("ui_manager.ReplayRecorder") as new_recorder,
            patch("simple_runner.run_simple") as runner,
        ):
            self.ui.simple_auto_checkbox.setChecked(True)
            analyze.assert_not_called()
            step.assert_not_called()
            self.assertFalse(self.ui.allow_guess_checkbox.isChecked())
            self.tick()
        step.assert_called_once_with(0, 0, Action.OPEN)
        self.assertEqual(analyze.call_count, 1)
        self.assertEqual(len(observations), 1)
        self.assertIs(self.ui._replay_recorder, recorder)
        self.assertEqual([(e.x, e.y, e.action) for e in recorder.events], [(0, 0, "OPEN")])
        self.assertIsNotNone(recorder.board)
        self.assertTrue(self.ui._timer_running)
        new_recorder.assert_not_called()
        runner.assert_not_called()

    def test_first_click_selection_reads_only_placement_boolean(self):
        with (
            patch.object(self.engine, "get_board_snapshot",
                         return_value=SimpleNamespace(mines_placed=False)),
            patch.object(self.ui, "_capture_replay_board_if_ready"),
            patch("core_engine.random.sample", return_value=[(1, 1)]),
            patch.object(self.engine, "step", wraps=self.engine.step) as step,
        ):
            self.ui.simple_auto_checkbox.setChecked(True)
            self.tick()
        step.assert_called_once_with(0, 0, Action.OPEN)

    def test_flag_unflag_all_hidden_is_normal_guess_and_never_forced_first_click(self):
        with patch("core_engine.random.sample", return_value=[(0, 0)]):
            self.ui.on_right_click(1, 1)
            self.ui.on_right_click(1, 1)
        before = self.engine.get_observation()
        self.assertTrue(all(value == CellState.HIDDEN for row in before for value in row))
        self.assertTrue(self.engine.get_board_snapshot().mines_placed)
        with (
            patch("ui_manager.analyze_position", wraps=analyze_position) as analyze,
            patch.object(self.engine, "step") as step,
        ):
            self.ui.simple_auto_checkbox.setChecked(True)
            self.tick()
        analyze.assert_called_once_with(before, 1)
        step.assert_not_called()
        self.assertEqual(len(self.ui._replay_recorder.events), 2)
        self.assertEqual(self.ui._analysis_result.decision.kind, DecisionKind.PROBABILITY_GUESS)
        self.assertTrue(self.ui.simple_auto_checkbox.isChecked())
        self.assertFalse(self.ui._simple_auto_timer.isActive())
        self.assertNotIn("첫 클릭", self.ui.analysis_status_label.text())

    def test_local_certainty_one_action_per_timeout_with_fresh_render_stats_and_analysis(self):
        self.prepare_board()
        self.ui.on_right_click(1, 1)
        snapshots = []
        order = []
        render = self.ui.render_board
        update_stats = self.ui._apply_stats_from_info

        def render_fresh():
            self.assert_clear()
            render()
            order.append("render")

        def stats_fresh(info):
            update_stats(info)
            order.append("stats")

        def analyze_fresh(observation, mines):
            self.assertEqual(observation, self.engine.get_observation())
            snapshots.append(observation)
            order.append("analyze")
            return analyze_position(observation, mines)

        with (
            patch("ui_manager.analyze_position", side_effect=analyze_fresh),
            patch("simple_decision.calculate_probabilities") as probabilities,
            patch("simple_probability.calculate_probabilities") as core_probabilities,
            patch.object(self.engine, "step", wraps=self.engine.step) as step,
        ):
            self.ui.simple_auto_checkbox.setChecked(True)
            self.assertEqual(self.ui._analysis_result.decision.kind, DecisionKind.LOCAL_DETERMINISTIC)
            with (
                patch.object(self.ui, "render_board", side_effect=render_fresh),
                patch.object(self.ui, "_apply_stats_from_info", side_effect=stats_fresh),
            ):
                for index in range(2):
                    move = self.ui._analysis_result.move
                    events_before = len(self.ui._replay_recorder.events)
                    order.clear()
                    self.tick()
                    self.assertEqual(step.call_count, index + 1)
                    self.assertEqual(step.call_args, call(move.x, move.y, move.action))
                    self.assertEqual(len(self.ui._replay_recorder.events), events_before + 1)
                    self.assertEqual(order, ["render", "stats", "analyze"])
                    self.assertTrue(self.ui._simple_auto_timer.isActive())
        self.assertEqual(len(snapshots), 3)
        self.assertNotEqual(snapshots[0], snapshots[1])
        self.assertNotEqual(snapshots[1], snapshots[2])
        probabilities.assert_not_called()
        core_probabilities.assert_not_called()

    def test_global_certainty_executes_existing_decision_move(self):
        # A flagged-only board has no local clues; the total budget proves safety.
        self.engine.reset_with_mines(3, 3, 1, {(1, 1)})
        self.ui.on_right_click(1, 1)
        with (
            patch("ui_manager.analyze_position", wraps=analyze_position) as analyze,
            patch.object(self.engine, "step", wraps=self.engine.step) as step,
        ):
            self.ui.simple_auto_checkbox.setChecked(True)
            decision = self.ui._analysis_result.decision
            self.assertEqual(decision.kind, DecisionKind.GLOBAL_CERTAINTY)
            self.tick()
        step.assert_called_once_with(decision.move.x, decision.move.y, decision.move.action)
        self.assertEqual(analyze.call_count, 2)
        self.assertEqual(analyze.call_args.args[0], self.engine.get_observation())

    def test_local_and_global_flags_record_once_then_analyze_the_new_flag(self):
        for mines, start, kind, target in (
            ({(1, 0), (2, 0)}, (0, 0), DecisionKind.LOCAL_DETERMINISTIC, (1, 0)),
            ({(0, 0), (3, 0), (4, 0)}, (1, 0), DecisionKind.GLOBAL_CERTAINTY, (3, 0)),
        ):
            with self.subTest(kind=kind):
                self.ui.analysis_checkbox.setChecked(False)
                self.ui._rebuild_game(5, 1, len(mines))
                self.engine.reset_with_mines(5, 1, len(mines), mines)
                self.ui.on_left_click(*start)
                recorder = self.ui._replay_recorder
                with (
                    patch("ui_manager.analyze_position", wraps=analyze_position) as analyze,
                    patch.object(self.engine, "step", wraps=self.engine.step) as step,
                ):
                    self.ui.simple_auto_checkbox.setChecked(True)
                    self.assertEqual(self.ui._analysis_result.decision.kind, kind)
                    self.tick()
                step.assert_called_once_with(*target, Action.FLAG)
                self.assertEqual(analyze.call_count, 2)
                observation = analyze.call_args.args[0]
                self.assertEqual(observation, self.engine.get_observation())
                self.assertEqual(observation[target[1]][target[0]], CellState.FLAGGED)
                self.assertIs(self.ui._replay_recorder, recorder)
                self.assertEqual(len(recorder.events), 2)
                self.assertEqual((recorder.events[-1].x, recorder.events[-1].y,
                                  recorder.events[-1].action), (*target, "FLAG"))

    def test_real_qt_timer_first_click_win_stops_without_analyzer(self):
        self.ui._rebuild_game(2, 1, 0)
        with (
            patch("ui_manager.analyze_position") as analyze,
            patch.object(self.engine, "step", wraps=self.engine.step) as step,
        ):
            self.ui.simple_auto_checkbox.setChecked(True)
            # Exercise Qt dispatch without waiting for wall-clock time.
            self.ui._simple_auto_timer.start(0)
            self.app.processEvents()
            self.app.processEvents()
        analyze.assert_not_called()
        step.assert_called_once_with(0, 0, Action.OPEN)
        self.assertEqual(self.engine.status, GameStatus.WON)
        self.assertEqual(len(self.ui._replay_recorder.events), 1)
        self.assert_stopped()

    def test_guess_pause_keeps_auto_overlay_recommendation_and_probability(self):
        self.engine.reset_with_mines(3, 3, 1, {(1, 1)})
        with patch.object(self.engine, "step") as step:
            self.ui.simple_auto_checkbox.setChecked(True)
            result = self.ui._analysis_result
            self.assertEqual(result.decision.kind, DecisionKind.PROBABILITY_GUESS)
            self.tick()
        step.assert_not_called()
        self.assertIs(self.ui._analysis_result, result)
        self.assertTrue(self.ui.simple_auto_checkbox.isChecked())
        self.assertFalse(self.ui._simple_auto_timer.isActive())
        self.assertIn("추측 대기", self.ui.analysis_status_label.text())
        button = self.ui._buttons[(result.move.x, result.move.y)]
        self.assertTrue(button.analysis_overlay.recommended)
        self.assertTrue(button.probability_text)

    def test_guess_acceptance_uses_original_tie_break_then_off_cancels_next_guess(self):
        self.prepare_board()
        first = recommendation(Action.OPEN, 2, 2, DecisionKind.PROBABILITY_GUESS)
        # All candidates tie; the UI must keep the analyzer's non-reading-order move.
        first = SimpleDecision(first.kind, first.move, (), first.deterministic_result,
                               ProbabilityResult(2, tuple(CellProbability(c, 1, 2)
                                                          for c in ((1, 0), (2, 2))),
                                                 (), ((1, 0), (2, 2))))
        second = recommendation(Action.OPEN, 2, 0, DecisionKind.PROBABILITY_GUESS)
        with (
            patch("ui_manager.analyze_position", side_effect=[first, second]) as analyze,
            patch("simple_probability.calculate_probabilities") as probabilities,
            patch("simple_probability.choose_probability_move") as choose,
            patch.object(self.engine, "step", wraps=self.engine.step) as step,
        ):
            self.ui.simple_auto_checkbox.setChecked(True)
            self.ui.allow_guess_checkbox.setChecked(True)
            self.assertEqual(analyze.call_count, 1)
            self.assertTrue(self.ui._simple_auto_timer.isActive())
            self.tick()
            step.assert_called_once_with(2, 2, Action.OPEN)
            self.assertEqual(analyze.call_count, 2)
            self.assertEqual(analyze.call_args.args[0], self.engine.get_observation())
            self.assertIs(self.ui._analysis_result.decision, second)
            self.assertTrue(self.ui._simple_auto_timer.isActive())
            self.ui.allow_guess_checkbox.setChecked(False)
            self.tick()
            step.assert_called_once_with(2, 2, Action.OPEN)
            self.assertEqual(analyze.call_count, 2)
        probabilities.assert_not_called()
        choose.assert_not_called()
        self.assertTrue(self.ui.simple_auto_checkbox.isChecked())
        self.assertFalse(self.ui._simple_auto_timer.isActive())
        self.assertIs(self.ui._analysis_result.decision, second)

    def test_manual_action_replaces_pending_recommendation_and_preserves_record_order(self):
        self.prepare_board()
        recorder = self.ui._replay_recorder
        first = recommendation(Action.OPEN, 2, 2)
        second = recommendation(Action.OPEN, 1, 0)
        third = recommendation(Action.OPEN, 2, 0)
        with (
            patch("ui_manager.analyze_position", side_effect=[first, second, third]) as analyze,
            patch.object(self.engine, "step", wraps=self.engine.step) as step,
            patch("ui_manager.ReplayRecorder") as new_recorder,
        ):
            self.ui.simple_auto_checkbox.setChecked(True)
            self.ui.on_left_click(2, 2)
            self.assertEqual(analyze.call_args.args[0], self.engine.get_observation())
            self.assertIs(self.ui._analysis_result.decision, second)
            self.assertTrue(self.ui._simple_auto_timer.isActive())
            self.tick()
        self.assertEqual(step.call_args_list, [call(2, 2, Action.OPEN), call(1, 0, Action.OPEN)])
        self.assertEqual(analyze.call_count, 3)
        self.assertIs(self.ui._replay_recorder, recorder)
        self.assertEqual([(e.x, e.y, e.action) for e in recorder.events],
                         [(0, 0, "OPEN"), (2, 2, "OPEN"), (1, 0, "OPEN")])
        self.assertEqual([e.elapsed_time for e in recorder.events],
                         sorted(e.elapsed_time for e in recorder.events))
        new_recorder.assert_not_called()
        player = ReplayPlayer(recorder.to_replay_data())
        player.go_to(player.event_count)
        self.assertEqual(player.engine.get_observation(), self.engine.get_observation())

    def test_human_guess_resumes_real_certainties(self):
        self.engine.reset_with_mines(3, 3, 1, {(1, 1)})
        self.ui.simple_auto_checkbox.setChecked(True)
        self.assertFalse(self.ui._simple_auto_timer.isActive())
        self.ui.on_left_click(0, 0)
        self.assertEqual(self.ui._analysis_result.decision.kind, DecisionKind.GLOBAL_CERTAINTY)
        move = self.ui._analysis_result.move
        with patch.object(self.engine, "step", wraps=self.engine.step) as step:
            self.tick()
        step.assert_called_once_with(move.x, move.y, move.action)
        self.assertTrue(self.ui.simple_auto_checkbox.isChecked())

    def test_invalid_moves_stop_without_step_or_loop(self):
        self.prepare_board()
        for move in (
            SimpleMove(Action.OPEN, 0, 0), SimpleMove(Action.FLAG, 0, 0),
            SimpleMove(Action.OPEN, -1, 0), SimpleMove(Action.FLAG, 3, 0),
            SimpleMove(Action.OPEN, 0, 3), SimpleMove(Action.CHORD, 1, 0),
            SimpleMove(Action.OPEN, 1.5, 0), SimpleMove(Action.OPEN, True, 0),
            SimpleMove("OPEN", 1, 0),
        ):
            with (
                self.subTest(move=move),
                patch("ui_manager.analyze_position", return_value=SimpleDecision(
                    DecisionKind.LOCAL_DETERMINISTIC, move, (), InferenceResult((), ()), None,
                )),
                patch.object(self.engine, "step") as step,
            ):
                self.ui.simple_auto_checkbox.setChecked(True)
                self.tick()
                self.tick()
                step.assert_not_called()
                self.assert_stopped()
                self.assert_clear()
                self.assertRegex(self.ui.analysis_status_label.text(), "자동 진행 중지|분석 불가")

    def test_timeout_revalidates_public_observation_including_hidden_target_staleness(self):
        self.prepare_board()
        for action, x, y in ((Action.OPEN, 2, 2), (Action.FLAG, 2, 2), (Action.FLAG, 1, 1)):
            with self.subTest(action=action, x=x, y=y):
                self.ui.analysis_checkbox.setChecked(False)
                self.ui.on_reset()
                self.prepare_board()
                with patch("ui_manager.analyze_position",
                           return_value=recommendation(Action.OPEN, 2, 2)):
                    self.ui.simple_auto_checkbox.setChecked(True)
                # Simulate unexpected external mutation without the UI refresh path.
                self.engine.step(x, y, action)
                with patch.object(self.engine, "step") as step:
                    self.tick()
                step.assert_not_called()
                self.assert_stopped()
                self.assertIn("일치하지", self.ui.analysis_status_label.text())

    def test_timeout_rechecks_first_click_placement_even_if_observation_matches(self):
        self.ui.simple_auto_checkbox.setChecked(True)
        self.engine.step(1, 1, Action.FLAG)
        self.engine.step(1, 1, Action.FLAG)
        with patch.object(self.engine, "step") as step:
            self.tick()
        step.assert_not_called()
        self.assert_stopped()
        self.assertIn("첫 클릭 추천", self.ui.analysis_status_label.text())

    def test_missing_or_unsupported_decision_stops(self):
        self.prepare_board()
        unsupported = recommendation(Action.OPEN, 1, 0, kind="unsupported")
        for decision in (None, unsupported):
            with (
                self.subTest(decision=decision),
                patch("ui_manager.analyze_position", return_value=decision),
                patch.object(self.engine, "step") as step,
            ):
                self.ui.simple_auto_checkbox.setChecked(True)
                self.tick()
                step.assert_not_called()
                self.assert_stopped()
                self.assert_clear()
                self.assertIn("자동 진행 중지", self.ui.analysis_status_label.text())

    def test_analysis_errors_cancel_existing_pending_action(self):
        self.prepare_board()
        for error in (InconsistentObservationError("bad flags"), ValueError("invalid"),
                      TypeError("invalid type"), RuntimeError("failed")):
            with self.subTest(error=error):
                with patch("ui_manager.analyze_position", return_value=recommendation(Action.OPEN, 1, 0)):
                    self.ui.simple_auto_checkbox.setChecked(True)
                self.assertTrue(self.ui._simple_auto_timer.isActive())
                with (
                    patch("ui_manager.analyze_position", side_effect=error),
                    patch.object(self.engine, "step") as step,
                ):
                    self.ui.analyze_button.click()
                    self.tick()
                step.assert_not_called()
                self.assert_stopped()
                self.assert_clear()
                self.assertIn("분석 불가", self.ui.analysis_status_label.text())

    def test_error_after_auto_action_adds_no_further_actions(self):
        self.prepare_board()
        with (
            patch("ui_manager.analyze_position", side_effect=[
                recommendation(Action.OPEN, 1, 0), RuntimeError("failed"),
            ]) as analyze,
            patch.object(self.engine, "step", wraps=self.engine.step) as step,
        ):
            self.ui.simple_auto_checkbox.setChecked(True)
            self.tick()
            self.tick()
        self.assertEqual(analyze.call_count, 2)
        step.assert_called_once_with(1, 0, Action.OPEN)
        self.assertEqual(len(self.ui._replay_recorder.events), 2)
        self.assert_stopped()
        self.assert_clear()

    def test_no_progress_or_step_exception_stops_without_reanalysis(self):
        self.prepare_board()
        for error in (None, RuntimeError("step failed")):
            with (
                self.subTest(error=error),
                patch("ui_manager.analyze_position", return_value=recommendation(Action.OPEN, 1, 0)) as analyze,
                patch.object(self.engine, "step", return_value=(None, 0, False, False, {}),
                             side_effect=error) as step,
            ):
                events_before = len(self.ui._replay_recorder.events)
                self.ui.simple_auto_checkbox.setChecked(True)
                self.tick()
                self.tick()
                step.assert_called_once_with(1, 0, Action.OPEN)
                self.assertEqual(analyze.call_count, 1)
                self.assertEqual(len(self.ui._replay_recorder.events), events_before + (error is None))
                self.assert_stopped()
                self.assertIn("자동 진행 중지", self.ui.analysis_status_label.text())

    def test_win_loss_stop_auto_guess_and_never_analyze_terminal(self):
        for status, target in ((GameStatus.WON, (0, 0)), (GameStatus.LOST, (1, 0))):
            with self.subTest(status=status):
                self.ui.analysis_checkbox.setChecked(False)
                self.ui._rebuild_game(2, 1, 1)
                self.engine.reset_with_mines(2, 1, 1, {(1, 0)})
                decision = recommendation(Action.OPEN, *target, DecisionKind.PROBABILITY_GUESS)
                with (
                    patch("ui_manager.analyze_position", return_value=decision) as analyze,
                    patch.object(self.engine, "step", wraps=self.engine.step) as step,
                ):
                    self.ui.simple_auto_checkbox.setChecked(True)
                    self.ui.allow_guess_checkbox.setChecked(True)
                    self.tick()
                    self.tick()
                    self.ui.simple_auto_checkbox.setChecked(True)
                    self.assert_stopped()
                step.assert_called_once_with(*target, Action.OPEN)
                self.assertEqual(analyze.call_count, 1)
                self.assertEqual(self.engine.status, status)
                self.assertTrue(self.ui._game_over)
                self.assertFalse(self.ui._timer_running)
                self.assert_clear()
                self.assertEqual(len(self.ui._replay_recorder.events), 1)

    def test_reset_difficulty_rebuild_and_close_cancel_pending(self):
        for transition in (self.ui.on_reset,
                           lambda: self.ui.on_difficulty_changed("초급 (9x9, 10)"),
                           lambda: self.ui._rebuild_game(3, 3, 1), self.ui.close):
            with self.subTest(transition=transition):
                self.ui.simple_auto_checkbox.setChecked(True)
                self.ui.allow_guess_checkbox.setChecked(True)
                self.assertTrue(self.ui._simple_auto_timer.isActive())
                with patch.object(self.engine, "step") as step:
                    transition()
                    self.tick()
                step.assert_not_called()
                self.assert_stopped()
                self.assertIs(self.ui.engine, self.engine)

    def test_custom_difficulty_stops_before_dialog_event_loop(self):
        self.ui.simple_auto_checkbox.setChecked(True)

        def dialog():
            self.assert_stopped()
            self.tick()
            return (3, 3, 1)

        with patch.object(self.ui, "_ask_custom_dimensions", side_effect=dialog):
            self.ui.on_difficulty_changed("커스텀")
        self.assert_stopped()

    def assert_replay_modal_stops_auto(self, entry, dialog_method, result):
        self.ui.simple_auto_checkbox.setChecked(True)
        self.ui.allow_guess_checkbox.setChecked(True)
        self.assertTrue(self.ui._simple_auto_pending)
        self.assertTrue(self.ui._simple_auto_timer.isActive())
        recorder = self.ui._replay_recorder
        analysis = self.ui._analysis_result

        def live_state():
            return (self.engine.get_observation(), self.engine.get_counter_snapshot(),
                    self.engine.get_board_snapshot(), recorder.board, recorder.events)

        before = live_state()

        def dialog(*args, **kwargs):
            self.assert_stopped()
            self.assertTrue(self.ui.analysis_checkbox.isChecked())
            self.assertIs(self.ui._analysis_result, analysis)
            # Deliver the canceled timeout through its real connected Qt signal.
            self.tick()
            self.assertEqual(live_state(), before)
            self.assert_stopped()
            return result

        with (
            patch("ui_manager." + dialog_method, side_effect=dialog) as modal,
            patch.object(self.engine, "step", wraps=self.engine.step) as step,
        ):
            entry()
            modal.assert_called_once()
            self.tick()
        step.assert_not_called()
        self.assertEqual(live_state(), before)
        self.assertIs(self.ui.engine, self.engine)
        self.assertIs(self.ui._replay_recorder, recorder)
        self.assert_stopped()

    def test_replay_file_dialogs_cancel_pending_live_auto(self):
        self.prepare_board()
        for entry, dialog_method, result in (
            (self.ui.on_save_replay, "QFileDialog.getExistingDirectory", ""),
            (self.ui.on_save_replay_as, "QFileDialog.getSaveFileName", ("", "")),
            (self.ui.on_load_replay, "QFileDialog.getOpenFileName", ("", "")),
        ):
            with self.subTest(entry=entry.__name__):
                self.assert_replay_modal_stops_auto(entry, dialog_method, result)
                self.assertFalse(self.ui._replay_mode)
                self.assertTrue(self.ui.simple_auto_checkbox.isEnabled())

    def test_replay_unavailable_messages_cancel_pending_live_auto(self):
        # Before the first click, Save/Save As show a message before any file dialog.
        for entry in (self.ui.on_save_replay, self.ui.on_save_replay_as):
            with self.subTest(entry=entry.__name__):
                self.assert_replay_modal_stops_auto(
                    entry, "QMessageBox.information", QMessageBox.Ok,
                )
                self.assertFalse(self.engine.get_board_snapshot().mines_placed)

    def test_replay_save_result_messages_cancel_pending_live_auto(self):
        self.prepare_board()
        with TemporaryDirectory() as directory:
            self.ui._last_replay_directory = directory
            for error, dialog_method in (
                (None, "QMessageBox.information"),
                (OSError("save failed"), "QMessageBox.warning"),
            ):
                with (
                    self.subTest(error=error),
                    patch("ui_manager.save_replay_json", side_effect=error) as save,
                    patch("ui_manager.QFileDialog.getExistingDirectory") as directory_dialog,
                ):
                    self.assert_replay_modal_stops_auto(
                        self.ui.on_save_replay, dialog_method, QMessageBox.Ok,
                    )
                    directory_dialog.assert_not_called()
                    save.assert_called_once()
                    self.assertEqual(save.call_args.args[0],
                                     self.ui._replay_recorder.to_replay_data())

    def test_replay_save_as_overwrite_dialog_cancels_pending_live_auto(self):
        self.prepare_board()
        with TemporaryDirectory() as directory:
            path = os.path.join(directory, "existing.json")
            with open(path, "w", encoding="utf-8") as replay_file:
                replay_file.write("unchanged")
            with (
                patch("ui_manager.QFileDialog.getSaveFileName", return_value=(path, "")),
                patch("ui_manager.save_replay_json") as save,
            ):
                self.assert_replay_modal_stops_auto(
                    self.ui.on_save_replay_as, "QMessageBox.question", QMessageBox.No,
                )
            save.assert_not_called()

    def test_replay_load_failure_message_cancels_pending_live_auto(self):
        self.prepare_board()
        with (
            patch("ui_manager.QFileDialog.getOpenFileName", return_value=("invalid.json", "")),
            patch("ui_manager.load_replay_json", side_effect=ValueError("invalid replay")),
        ):
            self.assert_replay_modal_stops_auto(
                self.ui.on_load_replay, "QMessageBox.warning", QMessageBox.Ok,
            )
        self.assertFalse(self.ui._replay_mode)

    def test_replay_load_success_cancels_pending_live_auto(self):
        self.prepare_board()
        replay = self.ui._replay_recorder.to_replay_data()
        with patch("ui_manager.load_replay_json", return_value=replay):
            self.assert_replay_modal_stops_auto(
                self.ui.on_load_replay, "QFileDialog.getOpenFileName", ("replay.json", ""),
            )
        self.assertTrue(self.ui._replay_mode)
        self.assertEqual(self.ui._replay_player.replay_data, replay)
        self.assertFalse(self.ui.simple_auto_checkbox.isEnabled())

    def test_replay_disables_auto_never_steps_either_engine_and_exit_stays_off(self):
        self.ui.simple_auto_checkbox.setChecked(True)
        self.ui.allow_guess_checkbox.setChecked(True)
        player = ReplayPlayer(ReplayData(
            ReplayBoard(3, 3, 1, {(1, 1)}),
            (ReplayEvent(1.0, 0, 0, "OPEN"), ReplayEvent(2.0, 1, 1, "FLAG")),
        ))
        before = self.engine.get_observation()
        with (
            patch("ui_manager.analyze_position") as analyze,
            patch.object(self.engine, "step") as live_step,
            patch.object(player.engine, "step", wraps=player.engine.step) as replay_step,
        ):
            self.ui._enter_replay_mode(player)
            self.assert_stopped()
            self.assertFalse(self.ui.simple_auto_checkbox.isEnabled())
            self.assertFalse(self.ui.allow_guess_checkbox.isEnabled())
            self.tick()
            self.ui.simple_auto_checkbox.setChecked(True)
            self.ui.allow_guess_checkbox.setChecked(True)
            self.ui.on_analyze_current()
            self.tick()
            live_step.assert_not_called()
            replay_step.assert_not_called()
            self.ui.on_replay_next()
            replay_step.assert_called_once_with(0, 0, Action.OPEN)
            self.assertEqual(self.engine.get_observation(), before)
            self.ui.on_exit_replay()
            self.tick()
        analyze.assert_not_called()
        live_step.assert_not_called()
        self.assertIs(self.ui.engine, self.engine)
        self.assertTrue(self.ui.simple_auto_checkbox.isEnabled())
        self.assertFalse(self.engine.get_board_snapshot().mines_placed)
        self.assert_stopped()


if __name__ == "__main__":
    unittest.main()
