"""Stage 2-4B: real Qt controls, engine and recorder; deterministic timeouts."""

import os
import unittest
from contextlib import contextmanager

from tests.ui_settings import isolate_ui_settings
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
    from PyQt5.QtCore import QAbstractEventDispatcher, Qt, QObject, pyqtSignal
    from PyQt5.QtTest import QSignalSpy, QTest
    from PyQt5.QtGui import QCloseEvent
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
        self.settings = isolate_ui_settings(self)
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

    def put_automatic_flag(self, x, y):
        # Exercise the unchanged normal planner path with an already-owned
        # automatic FLAG. External manual flags now go through preparation.
        self.ui.on_analyze_current()
        self.ui._apply_live_action(x, y, Action.FLAG, auto_observation=self.engine.get_observation())

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
        self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
        self.assertTrue(self.ui.allow_guess_checkbox.isChecked())
        self.assertFalse(self.ui._simple_auto_timer.isActive())
        self.assertTrue(self.ui.analysis_checkbox.isChecked())
        self.assertIsNotNone(self.ui._analysis_result)

    def test_interval_defaults_range_step_and_display(self):
        spin = self.ui.simple_auto_interval_spin
        self.assertEqual(spin.value(), 180)
        self.assertEqual(self.ui._simple_auto_timer.interval(), 180)
        self.assertEqual((spin.minimum(), spin.maximum(), spin.singleStep()), (0, 2000, 10))
        self.assertEqual(spin.text(), "180 ms")
        self.assertTrue(spin.isEnabled())
        self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
        for value, text in ((500, "500 ms"), (0, "최대 속도"), (2000, "2000 ms")):
            spin.setValue(value)
            self.assertEqual(spin.text(), text)
            self.assertEqual(self.ui._simple_auto_timer.interval(), value)
            self.assertFalse(self.ui._simple_auto_timer.isActive())
            self.assertFalse(self.ui._simple_auto_pending)
        self.assertEqual(spin.specialValueText(), "최대 속도")

    def test_focused_interval_keyboard_edit_refreshes_zero_and_numeric_text(self):
        spin = self.ui.simple_auto_interval_spin
        spin.setValue(500)
        self.ui.show()
        self.ui.activateWindow()
        spin.setFocus()
        self.app.processEvents()
        self.assertTrue(spin.hasFocus())
        changes = QSignalSpy(spin.valueChanged)
        with patch.object(self.engine, "step") as step:
            for value in (0, 180, 0, 500, 0, 2000, 0, 0):
                with self.subTest(value=value):
                    previous = spin.value()
                    change_count = len(changes)
                    QTest.keyClick(spin, Qt.Key_A, Qt.ControlModifier)
                    QTest.keyClicks(spin, str(value))
                    self.app.processEvents()
                    self.assertEqual(spin.value(), value)
                    self.assertEqual(spin.text(), "최대 속도" if value == 0 else f"{value} ms")
                    self.assertEqual(self.ui._simple_auto_timer.interval(), value)
                    self.assertTrue(spin.hasFocus())
                    self.assertFalse(self.ui._simple_auto_pending)
                    self.assertFalse(self.ui._simple_auto_timer.isActive())
                    step.assert_not_called()
                    if value == 0:
                        self.assertEqual(len(changes) - change_count, int(previous != 0))
            # Deleting the contents is intermediate input, not a committed zero.
            QTest.keyClick(spin, Qt.Key_A, Qt.ControlModifier)
            QTest.keyClick(spin, Qt.Key_Backspace)
            self.assertFalse(spin.hasAcceptableInput())
            QTest.keyClicks(spin, "500")
            self.app.processEvents()
            self.assertEqual(spin.value(), 500)
            self.assertEqual(spin.text(), "500 ms")
            self.assertEqual(self.ui._simple_auto_timer.interval(), 500)
            self.assertTrue(spin.hasFocus())
            step.assert_not_called()

    def test_focused_zero_edit_reschedules_one_pending_step_without_executing_it(self):
        self.prepare_board()
        self.ui.on_right_click(1, 1)
        spin = self.ui.simple_auto_interval_spin
        spin.setValue(500)
        self.ui.show()
        self.ui.activateWindow()
        spin.setFocus()
        self.app.processEvents()
        self.ui.simple_auto_checkbox.setChecked(True)
        result = self.ui._analysis_result
        timer = self.ui._simple_auto_timer
        changes = QSignalSpy(spin.valueChanged)
        with (patch("ui_manager.analyze_position", wraps=analyze_position) as analyze,
              patch.object(self.ui, "_simple_auto_move", wraps=self.ui._simple_auto_move) as select,
              patch.object(timer, "setInterval", wraps=timer.setInterval) as reschedule,
              patch.object(self.engine, "step", wraps=self.engine.step) as step):
            QTest.keyClick(spin, Qt.Key_A, Qt.ControlModifier)
            QTest.keyClicks(spin, "0")
            # Inspect before event dispatch: a pending zero timer may then move.
            self.assertEqual(spin.value(), 0)
            self.assertEqual(spin.text(), "최대 속도")
            self.assertTrue(spin.hasFocus())
            self.assertEqual(timer.interval(), 0)
            self.assertTrue(timer.isActive())
            self.assertTrue(self.ui._simple_auto_pending)
            self.assertIs(self.ui._analysis_result, result)
            registrations = QAbstractEventDispatcher.instance().registeredTimers(timer)
            self.assertEqual(len(registrations), 1)
            self.assertEqual(registrations[0].interval, 0)
            self.assertEqual(list(changes), [[0]])
            reschedule.assert_called_once_with(0)
            analyze.assert_not_called()
            select.assert_not_called()
            step.assert_not_called()
            self.tick()
            step.assert_called_once_with(result.move.x, result.move.y, result.move.action)
            analyze.assert_called_once_with(self.engine.get_observation(), self.engine.num_mines)
            self.assertTrue(self.ui._simple_auto_pending)
            self.assertTrue(timer.isActive())

    def test_interval_change_restarts_one_pending_timer_without_analysis_or_action(self):
        self.prepare_board()
        self.ui.on_right_click(1, 1)
        self.ui.simple_auto_checkbox.setChecked(True)
        timer = self.ui._simple_auto_timer
        result = self.ui._analysis_result
        observation = self.ui._analysis_observation
        with (patch("ui_manager.analyze_position") as analyze,
              patch.object(self.ui, "_simple_auto_move") as select,
              patch.object(self.engine, "step") as step):
            for interval in (500, 0, 2000, 180, 0):
                self.ui.simple_auto_interval_spin.setValue(interval)
                self.assertTrue(self.ui._simple_auto_pending)
                self.assertTrue(timer.isActive())
                self.assertTrue(timer.isSingleShot())
                self.assertEqual(timer.interval(), interval)
                registrations = QAbstractEventDispatcher.instance().registeredTimers(timer)
                self.assertEqual(len(registrations), 1)
                self.assertEqual(registrations[0].interval, interval)
                self.assertIs(self.ui._analysis_result, result)
                self.assertIs(self.ui._analysis_observation, observation)
            analyze.assert_not_called()
            select.assert_not_called()
            step.assert_not_called()
        with patch.object(self.engine, "step", wraps=self.engine.step) as step:
            self.tick()
        step.assert_called_once_with(result.move.x, result.move.y, result.move.action)
        self.assertTrue(self.ui._simple_auto_pending)
        self.assertEqual(timer.interval(), 0)

    def test_zero_interval_executes_one_move_per_timeout_and_analyzes_fresh(self):
        self.prepare_board()
        self.put_automatic_flag(1, 1)
        self.ui.simple_auto_interval_spin.setValue(0)
        self.ui.simple_auto_checkbox.setChecked(True)
        with (patch("ui_manager.analyze_position", wraps=analyze_position) as analyze,
              patch.object(self.engine, "step", wraps=self.engine.step) as step):
            for index in range(3):
                before = self.engine.get_observation()
                move = self.ui._analysis_result.move
                count = len(self.ui._replay_recorder.events)
                self.tick()
                self.assertEqual(step.call_count, index + 1)
                self.assertEqual(step.call_args, call(move.x, move.y, move.action))
                self.assertEqual(len(self.ui._replay_recorder.events), count + 1)
                self.assertEqual(analyze.call_count, index + 1)
                self.assertEqual(analyze.call_args.args[0], self.engine.get_observation())
                self.assertNotEqual(before, self.engine.get_observation())
                self.assertTrue(self.ui._simple_auto_pending)
                self.assertTrue(self.ui._simple_auto_timer.isActive())
                self.assertEqual(self.ui._simple_auto_timer.interval(), 0)

    def test_zero_interval_still_rejects_stale_public_state_at_timeout(self):
        self.prepare_board()
        self.ui.on_right_click(1, 1)
        self.ui.simple_auto_checkbox.setChecked(True)
        self.ui.simple_auto_interval_spin.setValue(0)
        self.engine.step(2, 2, Action.OPEN)
        with patch.object(self.engine, "step") as step:
            self.tick()
        step.assert_not_called()
        self.assert_stopped()
        self.assertIn("일치하지", self.ui.analysis_status_label.text())

    def test_interval_change_keeps_guess_wait_without_new_selection(self):
        self.engine.reset_with_mines(3, 3, 1, {(1, 1)})
        self.ui.simple_auto_checkbox.setChecked(True)
        self.assertEqual(self.ui._analysis_result.decision.kind, DecisionKind.PROBABILITY_GUESS)
        result = self.ui._analysis_result
        with (patch("ui_manager.analyze_position") as analyze,
              patch.object(self.ui, "_simple_auto_move") as select,
              patch.object(self.engine, "step") as step):
            self.ui.simple_auto_interval_spin.setValue(0)
            self.tick()
        analyze.assert_not_called()
        select.assert_not_called()
        step.assert_not_called()
        self.assertIs(self.ui._analysis_result, result)
        self.assertTrue(self.ui.simple_auto_checkbox.isChecked())
        self.assertFalse(self.ui._simple_auto_pending)
        self.assertFalse(self.ui._simple_auto_timer.isActive())

    def test_move_and_counters_are_invariant_across_intervals(self):
        for scenario in ("first", "local", "global", "guess"):
            expected = None
            for interval in (0, 180, 500, 2000):
                with self.subTest(scenario=scenario, interval=interval):
                    self.ui.analysis_checkbox.setChecked(False)
                    self.ui.on_reset()
                    if scenario != "first":
                        self.engine.reset_with_mines(3, 3, 1, {(1, 1)})
                        if scenario == "local":
                            self.ui.on_left_click(0, 0)
                        if scenario != "guess":
                            self.put_automatic_flag(1, 1)
                    self.ui.simple_auto_interval_spin.setValue(interval)
                    with patch("core_engine.random.sample", return_value=[(1, 1)]):
                        self.ui.simple_auto_checkbox.setChecked(True)
                        self.ui.allow_guess_checkbox.setChecked(scenario == "guess")
                        result = self.ui._analysis_result
                        kinds = {"local": DecisionKind.LOCAL_DETERMINISTIC,
                                 "global": DecisionKind.GLOBAL_CERTAINTY,
                                 "guess": DecisionKind.PROBABILITY_GUESS}
                        if scenario == "first":
                            self.assertTrue(self.ui._analysis_first_click)
                        else:
                            self.assertEqual(result.decision.kind, kinds[scenario])
                        self.tick()
                    last = self.ui._replay_recorder.events[-1]
                    actual = (result, (last.x, last.y, last.action),
                              self.engine.get_observation(), self.engine.get_counter_snapshot())
                    if expected is None:
                        expected = actual
                    self.assertEqual(actual, expected)
                    self.assertEqual((last.x, last.y, last.action),
                                     (result.move.x, result.move.y, result.move.action.name))

    def test_replay_disables_interval_and_exit_restores_editability(self):
        self.ui.simple_auto_interval_spin.setValue(500)
        player = ReplayPlayer(ReplayData(ReplayBoard(3, 3, 1, {(1, 1)}), ()))
        self.ui._enter_replay_mode(player)
        self.assertFalse(self.ui.simple_auto_interval_spin.isEnabled())
        self.assertFalse(self.ui.simple_auto_checkbox.isEnabled())
        for control in (self.ui.analysis_checkbox, self.ui.probability_checkbox,
                        self.ui.reduction_checkbox):
            self.assertTrue(control.isEnabled())
        self.ui.on_exit_replay()
        self.assertTrue(self.ui.simple_auto_interval_spin.isEnabled())
        self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
        self.assertEqual(self.ui.simple_auto_interval_spin.value(), 500)
        self.ui.simple_auto_interval_spin.setValue(0)
        self.assertEqual(self.ui._simple_auto_timer.interval(), 0)
        self.assertFalse(self.ui._simple_auto_timer.isActive())

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
        self.put_automatic_flag(1, 1)
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
        self.put_automatic_flag(1, 1)
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
            # Exercise the speed control and Qt dispatch without wall-clock waits.
            self.ui.simple_auto_interval_spin.setValue(0)
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
            patch("ui_manager.analyze_position", side_effect=[first, second, second, third]) as analyze,
            patch.object(self.engine, "step", wraps=self.engine.step) as step,
            patch("ui_manager.ReplayRecorder") as new_recorder,
        ):
            self.ui.simple_auto_checkbox.setChecked(True)
            self.ui.on_left_click(2, 2)
            self.assertEqual(analyze.call_args.args[0], self.engine.get_observation())
            self.assertIs(self.ui._analysis_result.decision, second)
            self.assertFalse(self.ui._simple_auto_timer.isActive())
            self.tick()
            self.ui.simple_auto_checkbox.setChecked(True)
            self.tick()
        self.assertEqual(step.call_args_list, [call(2, 2, Action.OPEN), call(1, 0, Action.OPEN)])
        self.assertEqual(analyze.call_count, 4)
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
        self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
        self.ui.simple_auto_checkbox.setChecked(True)
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
        self.assertIn("일치하지", self.ui.analysis_status_label.text())

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

    def test_auto_commit_followed_by_step_error_is_not_human_evidence(self):
        self.prepare_board()
        original = self.engine.step
        def committed_then_error(x, y, action):
            original(x, y, action)
            raise RuntimeError("after commit")
        with patch("ui_manager.analyze_position", return_value=recommendation(Action.OPEN, 1, 0)), \
                patch.object(self.engine, "step", side_effect=committed_then_error) as step:
            self.ui.simple_auto_checkbox.setChecked(True)
            self.tick()
            self.tick()
        self.assertEqual(step.call_count, 1)
        self.assertEqual(self.ui._replay_recorder.source_type, "algorithm")
        self.assertFalse(self.ui._mouse_trace_recorder.eligible)
        self.ui.on_reset()
        self.assertEqual(self.ui._replay_recorder.source_type, "human")

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
            (self.ui.replay_directory_action.trigger, "QFileDialog.getExistingDirectory", ""),
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
            self.settings.setValue("replay/default_directory", directory)
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


if QApplication is not None:
    class SyntheticLivePolicyJob(QObject):
        """UI seam only: no subprocess and no automatic policy execution."""
        proposal_ready = pyqtSignal(object)
        admitted = pyqtSignal(object)
        bootstrapped = pyqtSignal(object)
        acknowledged = pyqtSignal(object)
        finished = pyqtSignal(object)

        def __init__(self, parent=None):
            super().__init__(parent)
            self.state = "idle"
            self.active_run_id = None
            self.pending = None
            self.requests = []
            self.acks = []
            self.applied = []
            self.records = []
            self.last_record = None
            self.ack_error = None

        def start(self, snapshot):
            self.active_run_id = snapshot.run_id
            self.requests.append(snapshot)
            self.state = "computing"
            return snapshot.run_id

        def request(self, snapshot):
            if self.state != "ready":
                raise RuntimeError("request before ACKED")
            self.requests.append(snapshot)
            self.state = "computing"

        def deliver(self, proposal):
            self.pending = proposal
            self.state = "pending"
            self.proposal_ready.emit(proposal)

        def mark_applying(self, token):
            if self.state != "pending" or self.pending.token != token:
                raise RuntimeError("consumed token")
            self.state = "applying"
            self.applied.append(token)
            return self.pending

        def acknowledge(self, status, observation=None):
            from live_policy import make_ack
            if self.ack_error is not None:
                raise self.ack_error
            ack = make_ack(self.pending, status, observation)
            self.acks.append(ack)
            self.state = "acknowledging"

        def deliver_ack(self):
            ack = self.acks[-1]
            self.pending = None
            self.state = "ready"
            self.acknowledged.emit(ack)

        def cancel(self, reason="CANCELLED"):
            self.state = "cancelling"
            self.pending = None

        def complete_cancel(self, *, cleanup=True):
            record = {"run_id": self.active_run_id, "status": "CANCELLED",
                      "cleanup_complete": cleanup, "reaped": True,
                      "tree_active_count": 0}
            # Real _finish clears the active command identity even when failed
            # cleanup retains the same job/scope in state="blocked".
            self.active_run_id = None
            self.state = "idle" if cleanup else "blocked"
            self.records.append(record)
            self.finished.emit(record)

        def shutdown(self):
            self.active_run_id = None
            self.state = "closed"


@unittest.skipIf(QApplication is None, "PyQt5 unavailable")
class LiveV1UITests(unittest.TestCase):
    """Synthetic public states exercise real Main handlers, never public pilots."""
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.settings = isolate_ui_settings(self)
        for target, value in (("_ensure_zini_metric_job", None),):
            mock = patch.object(MinesweeperUI, target, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)
        job = patch("ui_manager.LivePolicyJob", SyntheticLivePolicyJob)
        job.start()
        self.addCleanup(job.stop)
        self.engine = MinesweeperEngine(9, 9, 10)
        self.ui = MinesweeperUI(self.engine)
        self.addCleanup(self.close_ui)
        from live_policy import POLICY_V1
        self.ui.live_policy_combo.setCurrentIndex(self.ui.live_policy_combo.findData(POLICY_V1))
        self.ui.on_reset()

    def close_ui(self):
        self.ui._stop_timer()
        self.ui.close()
        self.ui.deleteLater()
        self.app.processEvents()

    def start(self):
        self.ui.simple_auto_checkbox.setChecked(True)
        return self.ui._v1_job

    def tick(self):
        self.ui._simple_auto_timer.timeout.emit()

    def prepare_chord(self):
        """Install a named synthetic execution prefix after testing fresh admission."""
        from live_policy import plan_snapshot
        job = self.start()
        mines = {(2, 0), (2, 1), (6, 0), (8, 0), (6, 2), (8, 2),
                 (6, 4), (8, 4), (6, 6), (8, 6)}
        self.engine.reset_with_mines(9, 9, 10, mines)
        self.engine.step(1, 1, Action.OPEN)
        self.engine.step(2, 0, Action.FLAG)
        self.engine.step(2, 1, Action.FLAG)
        self.ui._live_fresh_reset = False
        self.ui._live_action_count = 3
        self.ui._v1_input_seq = 3
        self.ui._v1_cursor = (2, 1)
        proposal = plan_snapshot(self.ui._v1_snapshot())
        self.assertEqual(proposal.action, "CHORD")
        job.deliver(proposal)
        return job, proposal

    def test_policy_selection_stops_auto_and_changes_current_board_policy_without_execution(self):
        from live_policy import POLICY_SIMPLE, POLICY_V1
        self.assertEqual(self.ui._live_policy, POLICY_V1)
        game_id = self.ui._live_game_id
        before = self.engine.get_observation()
        self.ui.live_policy_combo.setCurrentIndex(0)
        self.assertEqual(self.ui._live_policy, POLICY_SIMPLE)
        self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
        self.assertEqual(self.ui._live_game_id, game_id)
        self.assertEqual(self.engine.get_observation(), before)
        self.assertEqual(self.ui._v1_job.requests, [])
        self.ui.on_reset()
        self.assertEqual(self.ui._live_policy, POLICY_SIMPLE)
        self.assertEqual(self.ui._replay_recorder.source_type, "human")
        self.assertTrue(self.ui.live_policy_combo.model().item(2).isEnabled())
        self.assertTrue(self.ui.live_policy_combo.model().item(3).isEnabled())
        self.assertFalse(self.ui.live_policy_combo.model().item(4).isEnabled())

    def test_initial_proposal_pause_resume_and_rate_reuse_without_simple_analysis(self):
        from live_policy import plan_snapshot
        with patch("ui_manager.analyze_position") as simple:
            job = self.start()
            proposal = plan_snapshot(job.requests[-1])
            self.ui.simple_auto_checkbox.setChecked(False)
            job.deliver(proposal)
            self.assertFalse(self.ui._simple_auto_timer.isActive())
            self.assertEqual(self.ui._replay_recorder.source_type, "human")
            self.ui.simple_auto_interval_spin.setValue(0)
            self.ui.on_analyze_current()
            self.ui.simple_auto_checkbox.setChecked(True)
            self.assertTrue(self.ui._simple_auto_timer.isActive())
            self.assertIs(self.ui._v1_pending, proposal)
            self.assertEqual(len(job.requests), 1)
            self.assertFalse(self.ui.allow_guess_checkbox.isChecked())
        simple.assert_not_called()

    def test_manual_analysis_displays_once_when_analysis_toggle_is_off(self):
        from live_policy import plan_snapshot
        self.assertFalse(self.ui.analysis_checkbox.isChecked())
        self.ui.on_analyze_current()
        job = self.ui._v1_job
        proposal = plan_snapshot(job.requests[-1])
        job.deliver(proposal)
        self.assertIsNotNone(self.ui._analysis_result)
        self.assertIn("Stage3 V1", self.ui.analysis_status_label.text())
        self.assertFalse(self.ui._simple_auto_timer.isActive())
        self.assertEqual(len(job.requests), 1)

    def test_auxiliary_close_refusal_restores_only_a_clean_live_owner(self):
        original_job = self.ui._v1_job
        self.ui._stage3_visualizer_launcher = SimpleNamespace(close=lambda: False)
        try:
            event = QCloseEvent()
            self.ui.closeEvent(event)
            self.assertFalse(event.isAccepted())
            self.assertFalse(self.ui._live_closing)
            self.assertIsNot(self.ui._v1_job, original_job)
            self.assertEqual(self.ui._v1_job.state, "idle")
            self.assertFalse(self.ui._v1_manual_only)
            self.ui.on_reset()
            job = self.start()
            self.assertEqual(len(job.requests), 1)
        finally:
            self.ui._stage3_visualizer_launcher = None

    def test_live_cleanup_failure_does_not_replace_owned_job(self):
        job = self.ui._v1_job
        with patch.object(job, "shutdown", side_effect=RuntimeError("cleanup blocked")):
            event = QCloseEvent()
            self.ui.closeEvent(event)
        self.assertFalse(event.isAccepted())
        self.assertTrue(self.ui._live_closing)
        self.assertIs(self.ui._v1_job, job)

    def test_initial_admission_rejects_fixed_hidden_and_missing_reset(self):
        self.engine.reset_with_mines(9, 9, 10, {(x, 8) for x in range(9)} | {(8, 7)})
        job = self.start()
        self.assertEqual(job.requests, [])
        self.assertTrue(self.ui._v1_manual_only)
        self.assertEqual(self.ui._replay_recorder.events, ())

    def test_initial_timeout_rechecks_placement_after_pending(self):
        from live_policy import plan_snapshot
        job = self.start()
        job.deliver(plan_snapshot(job.requests[-1]))
        self.engine.reset_with_mines(9, 9, 10, {(x, 8) for x in range(9)} | {(8, 7)})
        with patch.object(self.engine, "step") as step:
            self.tick()
        step.assert_not_called()
        self.assertTrue(self.ui._v1_manual_only)

    def test_custom_and_progressed_domains_never_start(self):
        self.ui._rebuild_game(8, 8, 10)
        job = self.start()
        self.assertEqual(job.requests, [])
        self.assertFalse(self.ui.simple_auto_checkbox.isEnabled())

    def test_chord_actual_first_input_token_consumed_before_step_and_ack(self):
        job, proposal = self.prepare_chord()
        original = self.engine.step
        calls = []
        def step(x, y, action):
            self.assertEqual(job.state, "applying")
            self.assertIsNone(self.ui._v1_pending)
            calls.append((x, y, action))
            return original(x, y, action)
        with patch.object(self.engine, "step", side_effect=step), patch("ui_manager.analyze_position") as simple:
            self.tick()
            self.tick()
        self.assertEqual(calls, [(proposal.x, proposal.y, Action.CHORD)])
        self.assertEqual(len(job.requests), 1)
        self.assertEqual(len(job.acks), 1)
        self.assertEqual(len(self.ui._replay_recorder.events), 1)
        self.assertEqual(self.ui._replay_recorder.source_type, "algorithm")
        self.assertEqual(len(self.ui.live_action_records), 1)
        self.assertTrue(self.ui.live_action_records[0]["ack_sent"])
        simple.assert_not_called()
        job.deliver_ack()
        self.assertEqual(len(job.requests), 2)

    def test_pause_after_apply_waits_for_ack_and_reuses_ready_state(self):
        job, _ = self.prepare_chord()
        self.tick()
        self.ui.simple_auto_checkbox.setChecked(False)
        job.deliver_ack()
        self.assertEqual(len(job.requests), 1)
        self.ui.simple_auto_checkbox.setChecked(True)
        self.assertEqual(len(job.requests), 2)

    def test_guess_wait_and_allow_toggle_keep_single_pending_decision(self):
        from live_policy import plan_snapshot
        job = self.start()
        self.engine.reset_with_mines(9, 9, 10, {(1, 1)} | {(x, 8) for x in range(9)})
        self.engine.step(0, 0, Action.OPEN)
        self.ui._live_fresh_reset = False
        self.ui._live_action_count = 1
        self.ui._v1_input_seq = 1
        proposal = plan_snapshot(self.ui._v1_snapshot())
        self.assertTrue(proposal.is_guess)
        job.deliver(proposal)
        self.assertFalse(self.ui._simple_auto_timer.isActive())
        self.assertIn("추측 대기", self.ui.live_policy_status_label.text())
        self.ui.simple_auto_interval_spin.setValue(500)
        self.ui.on_analyze_current()
        self.ui.allow_guess_checkbox.setChecked(True)
        self.assertTrue(self.ui._simple_auto_timer.isActive())
        self.assertIs(self.ui._v1_pending, proposal)
        self.assertEqual(len(job.requests), 1)

    def test_ack_failure_cannot_repeat_actual_input(self):
        job, _ = self.prepare_chord()
        job.ack_error = RuntimeError("synthetic ACK loss")
        with patch.object(self.engine, "step", wraps=self.engine.step) as step:
            self.tick()
            self.tick()
            self.ui.simple_auto_checkbox.setChecked(True)
            self.tick()
        self.assertEqual(step.call_count, 1)
        self.assertEqual(len(self.ui._replay_recorder.events), 1)
        self.assertFalse(self.ui.live_action_records[0]["ack_sent"])
        self.assertTrue(self.ui._v1_manual_only)

    def test_same_observation_different_generation_rejects_pending(self):
        job, _ = self.prepare_chord()
        self.ui._live_board_generation += 1
        with patch.object(self.engine, "step") as step:
            self.tick()
        step.assert_not_called()
        self.assertEqual(job.applied, [])

    def test_same_token_different_valid_action_is_not_executed(self):
        from dataclasses import replace
        job, proposal = self.prepare_chord()
        alternate = next(cell for cell in proposal.overlays if cell.kind == "safe")
        forged = replace(proposal, action="OPEN", x=alternate.x, y=alternate.y)
        self.ui._v1_pending = forged
        with patch.object(self.engine, "step") as step:
            self.tick()
        step.assert_not_called()
        self.assertEqual(job.applied, [proposal.token])
        self.assertTrue(self.ui._v1_manual_only)

    def test_manual_input_retires_owner_and_cleanup_allows_same_board_restart(self):
        from live_policy import ADOPT_CURRENT
        job, _ = self.prepare_chord()
        previous_run = self.ui._live_run_id
        generation = self.ui._live_board_generation
        with patch.object(self.engine, "step", wraps=self.engine.step) as step:
            self.ui.on_right_click(0, 0)
            self.assertGreater(self.ui._live_board_generation, generation)
            self.assertEqual(step.call_count, 1)
        self.ui.simple_auto_checkbox.setChecked(True)
        self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
        self.assertEqual(len(job.requests), 1)
        self.assertFalse(self.ui._v1_manual_only)
        self.assertEqual(job.acks, [])
        job.complete_cancel()
        self.ui.simple_auto_checkbox.setChecked(True)
        self.assertEqual(len(job.requests), 2)
        self.assertEqual(job.requests[-1].entry_mode, ADOPT_CURRENT)
        self.assertEqual(job.requests[-1].input_seq, 0)
        self.assertEqual(job.requests[-1].input_revision, 4)
        self.assertEqual(job.requests[-1].cursor, (0, 0))
        self.assertNotEqual(job.requests[-1].run_id, previous_run)

    def test_reset_and_replay_reject_late_proposals(self):
        job, proposal = self.prepare_chord()
        self.ui.on_reset()
        job.proposal_ready.emit(proposal)
        self.assertIsNone(self.ui._v1_pending)
        player = ReplayPlayer(ReplayData(ReplayBoard(3, 3, 1, {(1, 1)}), (ReplayEvent(1, 0, 0, "OPEN"),)))
        self.ui._enter_replay_mode(player)
        job.proposal_ready.emit(proposal)
        self.assertIsNone(self.ui._v1_pending)
        self.assertFalse(self.ui.simple_auto_checkbox.isEnabled())
        self.assertEqual(self.ui.live_policy_status_label.text(), "알고리즘 사용 기록: 없음")

    def test_all_new_game_policy_pairs_clear_guess_without_old_owner_signals(self):
        from live_policy import POLICY_SIMPLE, POLICY_V1
        for previous in (POLICY_SIMPLE, POLICY_V1):
            for selected in (POLICY_SIMPLE, POLICY_V1):
                with self.subTest(previous=previous, selected=selected):
                    self.ui._v1_job.active_run_id = None  # Prior synthetic owner is reaped.
                    self.ui._v1_job.state = "idle"
                    self.ui.live_policy_combo.setCurrentIndex(self.ui.live_policy_combo.findData(previous))
                    self.ui.on_reset()
                    job = self.start()
                    self.ui.allow_guess_checkbox.setChecked(True)
                    identity = self.ui._live_run_id
                    requests = len(job.requests)
                    signal = QSignalSpy(self.ui.allow_guess_checkbox.toggled)
                    self.ui.live_policy_combo.setCurrentIndex(self.ui.live_policy_combo.findData(selected))
                    self.assertEqual(self.ui._live_run_id, identity)
                    self.assertEqual(self.ui._live_policy, selected)
                    self.assertEqual(self.ui.allow_guess_checkbox.isChecked(), previous == selected)
                    self.ui.on_reset()
                    self.assertEqual(self.ui._live_policy, selected)
                    self.assertNotEqual(self.ui._live_run_id, identity)
                    self.assertFalse(self.ui.allow_guess_checkbox.isChecked())
                    self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
                    self.assertFalse(self.ui._simple_auto_timer.isActive())
                    self.assertEqual(len(signal), 0)
                    self.assertEqual(len(job.requests), requests)
                    self.assertEqual(self.ui._replay_recorder.events, ())

    def test_difficulty_new_live_board_clears_guess_for_both_policies(self):
        from live_policy import POLICY_SIMPLE, POLICY_V1
        for policy in (POLICY_SIMPLE, POLICY_V1):
            with self.subTest(policy=policy):
                self.ui._v1_job.active_run_id = None
                self.ui._v1_job.state = "idle"
                self.ui.live_policy_combo.setCurrentIndex(self.ui.live_policy_combo.findData(policy))
                self.ui.on_reset()
                self.start()
                self.ui.allow_guess_checkbox.setChecked(True)
                self.ui.on_difficulty_changed("중급 (16x16, 40)")
                self.assertEqual((self.engine.width, self.engine.height, self.engine.num_mines), (16, 16, 40))
                self.assertFalse(self.ui.allow_guess_checkbox.isChecked())
                self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
                self.assertFalse(self.engine.get_board_snapshot().mines_placed)

    def test_replay_exit_new_live_board_clears_guess_for_both_policies(self):
        from live_policy import POLICY_SIMPLE, POLICY_V1
        for policy in (POLICY_SIMPLE, POLICY_V1):
            with self.subTest(policy=policy):
                self.ui._v1_job.active_run_id = None
                self.ui._v1_job.state = "idle"
                self.ui.live_policy_combo.setCurrentIndex(self.ui.live_policy_combo.findData(policy))
                self.ui.on_reset()
                self.start()
                self.ui.allow_guess_checkbox.setChecked(True)
                player = ReplayPlayer(ReplayData(ReplayBoard(3, 3, 1, {(1, 1)}), ()))
                self.ui._enter_replay_mode(player)
                self.ui.on_exit_replay()
                self.assertFalse(self.ui._replay_mode)
                self.assertFalse(self.ui.allow_guess_checkbox.isChecked())
                self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
                self.assertFalse(self.engine.get_board_snapshot().mines_placed)
                self.assertEqual(self.ui._replay_recorder.source_type, "human")

    def test_v1_pause_keeps_guess_pending_but_selector_retires_owner(self):
        from live_policy import plan_snapshot
        job = self.start()
        self.engine.reset_with_mines(9, 9, 10, {(1, 1)} | {(x, 8) for x in range(9)})
        self.engine.step(0, 0, Action.OPEN)
        self.ui._live_fresh_reset = False
        self.ui._live_action_count = self.ui._v1_input_seq = 1
        proposal = plan_snapshot(self.ui._v1_snapshot())
        self.assertTrue(proposal.is_guess)
        job.deliver(proposal)
        self.ui.allow_guess_checkbox.setChecked(True)
        identity = (self.ui._live_run_id, self.ui._live_board_generation)
        self.ui.simple_auto_checkbox.setChecked(False)
        self.assertTrue(self.ui.allow_guess_checkbox.isChecked())
        self.assertFalse(self.ui._simple_auto_timer.isActive())
        self.ui.simple_auto_checkbox.setChecked(True)
        self.assertTrue(self.ui.allow_guess_checkbox.isChecked())
        self.assertIs(self.ui._v1_pending, proposal)
        self.assertEqual((self.ui._live_run_id, self.ui._live_board_generation), identity)
        self.assertEqual(len(job.requests), 1)
        self.assertTrue(self.ui._simple_auto_timer.isActive())
        self.assertEqual(job.applied, [])
        self.ui.live_policy_combo.setCurrentIndex(0)
        self.assertFalse(self.ui.allow_guess_checkbox.isChecked())
        self.assertIsNone(self.ui._v1_pending)
        self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
        self.assertEqual(self.ui._live_run_id, identity[0])
        self.assertGreater(self.ui._live_board_generation, identity[1])
        self.assertEqual(job.state, "cancelling")
        self.assertEqual(len(job.requests), 1)

    def test_new_v1_guess_off_allows_initial_but_blocks_next_guess(self):
        from live_policy import plan_snapshot
        job = self.start()
        self.ui.allow_guess_checkbox.setChecked(True)
        self.ui.on_reset()
        job.active_run_id, job.state = None, "idle"  # Complete synthetic cancellation.
        self.start()
        initial = plan_snapshot(job.requests[-1])
        job.deliver(initial)
        self.assertEqual((initial.action, initial.x, initial.y, initial.kind), ("OPEN", 0, 0, "initial"))
        self.assertFalse(self.ui.allow_guess_checkbox.isChecked())
        self.assertTrue(self.ui._simple_auto_timer.isActive())
        self.ui.simple_auto_checkbox.setChecked(False)
        # Small fixed public prefix seam, not a production fresh-admission bypass.
        self.engine.reset_with_mines(9, 9, 10, {(1, 1)} | {(x, 8) for x in range(9)})
        self.engine.step(0, 0, Action.OPEN)
        self.ui._live_fresh_reset = False
        self.ui._live_action_count = self.ui._v1_input_seq = 1
        self.ui._v1_pending = job.pending = None
        job.state = "computing"
        self.ui.simple_auto_checkbox.setChecked(True)
        guess = plan_snapshot(self.ui._v1_snapshot())
        self.assertTrue(guess.is_guess)
        job.deliver(guess)
        self.assertFalse(self.ui._simple_auto_timer.isActive())
        self.assertIn("추측 대기", self.ui.live_policy_status_label.text())
        with patch.object(self.engine, "step") as step:
            self.tick()
        step.assert_not_called()

    def test_replay_labels_use_recorded_source_not_selected_policy(self):
        from replay_model import SOURCE_AI, SOURCE_ALGORITHM, SOURCE_HUMAN
        for source in (SOURCE_AI, SOURCE_ALGORITHM, SOURCE_HUMAN):
            with self.subTest(source=source):
                data = ReplayData(ReplayBoard(3, 3, 1, {(1, 1)}), (), source_type=source)
                self.ui._enter_replay_mode(ReplayPlayer(data))
                label = self.ui.live_policy_status_label.text()
                self.assertEqual(label, "알고리즘 사용 기록: " + ("없음" if source == SOURCE_HUMAN else "있음"))
                self.assertTrue(self.ui.live_policy_combo.isHidden())
                self.assertNotIn("Stage3 V1", label)
                self.assertEqual(self.ui._replay_data.source_type, source)

    @contextmanager
    def terminal_fixture(self, status):
        """Real final input on tiny fixed public prefixes; synthetic job only."""
        from live_policy import plan_snapshot
        self.ui._v1_job.active_run_id, self.ui._v1_job.state = None, "idle"
        self.ui._rebuild_game(9, 9, 10)
        job = self.start()
        if status == GameStatus.WON:
            self.engine.reset_with_mines(4, 1, 1, {(1, 0)})
            prefix = [(0, Action.OPEN), (1, Action.FLAG), (2, Action.OPEN)]
        else:
            self.engine.reset_with_mines(5, 1, 2, {(1, 0), (2, 0)})
            prefix = [(0, Action.OPEN), (1, Action.FLAG)]
        for x, action in prefix:
            self.engine.step(x, 0, action)
        self.ui._reset_replay_recorder()
        self.ui._live_fresh_reset = False
        self.ui._live_action_count = self.ui._v1_input_seq = len(prefix)
        self.ui._v1_cursor = (prefix[-1][0], 0)
        self.ui.allow_guess_checkbox.setChecked(True)
        proposal = plan_snapshot(self.ui._v1_snapshot())
        job.deliver(proposal)
        self.tick()
        self.assertEqual(self.engine.status, status)
        self.assertEqual(len(self.ui.live_action_records), 1)
        self.assertEqual(len(self.ui._replay_recorder.events), 1)
        # Only terminal display uses the preset seam for this tiny fixture.
        # Fresh admission and the actual input above run before this patch.
        with patch.object(self.ui, "_v1_supported", return_value=True):
            self.ui._update_policy_controls()
            yield job

    def test_terminal_exit_failure_preserves_won_lost_and_records(self):
        from copy import deepcopy
        for status in (GameStatus.WON, GameStatus.LOST):
            for clean in (True, False):
                with self.subTest(status=status, cleanup=clean), self.terminal_fixture(status) as job:
                    before = (self.engine.get_counter_snapshot(), self.ui._replay_recorder.events,
                              deepcopy(self.ui.live_action_records), self.engine.get_observation())
                    job.active_run_id, job.state = None, "idle" if clean else "blocked"
                    record = {"run_id": self.ui._live_run_id, "status": "FAILED",
                              "error": "FINISH_EXIT_TIMEOUT: launcher not reaped" + ("" if clean else "\nCLEANUP: busy"),
                              "cleanup_complete": clean, "terminal": {"status": status.name}}
                    self.ui._on_v1_finished(record)
                    self.assertEqual(self.engine.status, status)
                    self.assertEqual(before, (self.engine.get_counter_snapshot(), self.ui._replay_recorder.events,
                                             self.ui.live_action_records, self.engine.get_observation()))
                    self.assertEqual(self.ui._replay_recorder.source_type, "algorithm")
                    self.assertIn(status.name + " · worker 종료 지연", self.ui.live_policy_status_label.text())
                    self.assertIn("정리 완료" if clean else "정리 실패", self.ui.live_policy_status_label.text())
                    self.assertIn("FINISH_EXIT_TIMEOUT", self.ui.analysis_status_label.text())
                    self.assertFalse(self.ui.simple_auto_checkbox.isEnabled())
                    self.assertEqual(job.state, "idle" if clean else "blocked")

    def test_terminal_stale_or_failed_receipt_not_promoted_and_success_unchanged(self):
        for status in (GameStatus.WON, GameStatus.LOST):
            with self.subTest(status=status):
                with self.terminal_fixture(status) as job:
                    label = self.ui.live_policy_status_label.text()
                    self.ui._on_v1_finished({"run_id": "stale", "status": "SUCCEEDED"})
                    self.assertEqual(self.ui.live_policy_status_label.text(), label)
                    self.assertTrue(self.ui._v1_owned)
                    job.active_run_id, job.state = None, "idle"
                    self.ui._on_v1_finished({"run_id": self.ui._live_run_id, "status": "SUCCEEDED",
                                             "cleanup_complete": True, "terminal": {"status": status.name}})
                    self.assertIn(status.name + " · 정리 완료", self.ui.live_policy_status_label.text())
                    self.assertNotIn("worker 실패", self.ui.live_policy_status_label.text())
                    self.assertFalse(self.ui._v1_owned)
                with self.terminal_fixture(status) as job:
                    job.active_run_id, job.state = None, "idle"
                    self.ui._on_v1_finished({"run_id": self.ui._live_run_id, "status": "FAILED",
                                             "cleanup_complete": True, "error": "REPLY_TRANSPORT: invalid terminal"})
                    self.assertIn(status.name + " · worker 실패", self.ui.live_policy_status_label.text())
                    self.assertIn("invalid terminal", self.ui.analysis_status_label.text())
                    self.assertEqual(self.engine.status, status)

    def test_new_v1_manual_flag_is_human_then_analysis_only_reviews_without_input(self):
        from live_policy import ADOPT_CURRENT, PHASE_FLAG_REVIEW, plan_snapshot
        self.assertFalse(self.ui._v1_board_locked())
        self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
        self.assertFalse(self.ui.allow_guess_checkbox.isChecked())
        self.ui.on_right_click(4, 5)
        before = (self.engine.get_observation(), self.ui._replay_recorder.events,
                  self.ui._replay_recorder.source_type, dict(self.ui.live_auto_totals))
        self.ui.on_analyze_current()
        job = self.ui._v1_job
        snapshot = job.requests[-1]
        self.assertEqual((snapshot.entry_mode, snapshot.phase, snapshot.input_seq,
                          snapshot.input_revision, snapshot.cursor),
                         (ADOPT_CURRENT, PHASE_FLAG_REVIEW, 0, 1, (4, 5)))
        proposal = plan_snapshot(snapshot)
        self.assertTrue(proposal.is_flag_review)
        job.deliver(proposal)
        self.tick()
        self.assertEqual(before, (self.engine.get_observation(), self.ui._replay_recorder.events,
                                  self.ui._replay_recorder.source_type, self.ui.live_auto_totals))
        self.assertEqual(job.applied, [])
        self.assertIn("미확인 깃발 해제", self.ui.analysis_status_label.text())
        self.assertTrue(all(cell.kind is None and cell.probability is None
                            for cell in self.ui._analysis_result.overlays.values()))

    def test_first_preparation_unflag_is_recorded_costed_and_then_guess_off_waits(self):
        from live_policy import PHASE_V1, plan_snapshot
        from stage3_physical import action_cost, load_timing_table
        self.ui.on_right_click(4, 5)
        job = self.start()
        proposal = plan_snapshot(job.requests[-1])
        self.assertEqual(proposal.review.unverified, ((4, 5),))
        job.deliver(proposal)
        with patch.object(self.engine, "step", wraps=self.engine.step) as step:
            self.tick()
            self.tick()
        step.assert_called_once_with(4, 5, Action.FLAG)
        self.assertTrue(all(value == CellState.HIDDEN for row in self.engine.get_observation() for value in row))
        self.assertEqual([event.action for event in self.ui._replay_recorder.events], ["FLAG", "FLAG"])
        self.assertEqual(self.ui._replay_recorder.source_type, "algorithm")
        self.assertFalse(self.ui._mouse_trace_recorder.eligible)
        record = self.ui.live_action_records[-1]
        self.assertEqual((record["semantic_input"], record["input_revision_before"],
                          record["input_revision_after"], record["event_index"]), ("UNFLAG", 1, 2, 1))
        self.assertEqual(record["modeled_action_us"], action_cost(load_timing_table(), (4, 5), (4, 5)))
        self.assertGreater(record["modeled_action_us"], 0)
        self.assertEqual(record["compute_ns"], 0)
        self.assertTrue(record["ack_sent"])
        self.assertEqual(self.ui.live_auto_totals["preparation_inputs"], 1)
        self.assertEqual(self.ui.live_auto_totals["v1_inputs"], 0)
        self.assertEqual(self.ui.live_auto_totals["auto_inputs"], 1)
        self.assertEqual(self.ui._v1_phase, PHASE_V1)
        job.deliver_ack()
        guess = plan_snapshot(job.requests[-1])
        self.assertTrue(guess.is_guess)
        job.deliver(guess)
        self.tick()
        self.assertEqual(len(self.ui._replay_recorder.events), 2)
        self.assertEqual(job.applied, [proposal.token])
        self.assertIn("추측 대기", self.ui.live_policy_status_label.text())

    def test_fifty_fifty_unflag_has_no_open_and_no_guess_bypass(self):
        from live_policy import ADOPT_CURRENT, PHASE_FLAG_REVIEW, plan_snapshot
        # Named tiny execution seam after real preset admission, like prepare_chord.
        job = self.start()
        self.engine.reset_with_mines(3, 1, 1, {(0, 0)})
        self.engine.step(1, 0, Action.OPEN)
        self.engine.step(0, 0, Action.FLAG)
        self.ui._reset_replay_recorder()
        self.ui._live_fresh_reset = False
        self.ui._live_action_count = 2
        self.ui._v1_cursor = (0, 0)
        self.ui._v1_entry_mode = ADOPT_CURRENT
        self.ui._v1_phase = PHASE_FLAG_REVIEW
        self.ui._v1_initial_flag_count = 1
        proposal = plan_snapshot(self.ui._v1_snapshot())
        self.assertEqual(proposal.review.unverified, ((0, 0),))
        job.deliver(proposal)
        self.tick()
        self.assertEqual(self.engine.get_observation(), [[CellState.HIDDEN, 1, CellState.HIDDEN]])
        job.deliver_ack()
        guess = plan_snapshot(job.requests[-1])
        self.assertTrue(guess.is_guess)
        target = next(cell for cell in guess.overlays if (cell.x, cell.y) == (guess.x, guess.y))
        self.assertEqual(target.mine_worlds * 2, target.total_worlds)
        job.deliver(guess)
        self.tick()
        self.assertEqual([event.action for event in self.ui._replay_recorder.events], ["FLAG"])
        self.assertEqual(len(job.applied), 1)

    def test_preparation_pause_reuses_review_and_manual_input_discards_remaining_work(self):
        from live_policy import plan_snapshot
        self.ui.on_right_click(1, 0)
        self.ui.on_right_click(0, 0)
        job = self.start()
        first = plan_snapshot(job.requests[-1])
        self.assertEqual((first.x, first.y), (0, 0))
        job.deliver(first)
        self.tick()
        self.ui.simple_auto_checkbox.setChecked(False)
        job.deliver_ack()
        self.assertEqual(len(job.requests), 1)
        self.ui.simple_auto_checkbox.setChecked(True)
        with patch("live_policy.review_flags", side_effect=AssertionError("review repeated")):
            second = plan_snapshot(job.requests[-1], review=first.review)
        self.assertEqual((second.x, second.y, second.review_compute_ns), (1, 0, 0))
        job.deliver(second)
        old_callback = self.ui._simple_auto_timeout_slot
        self.ui.on_right_click(2, 0)
        self.assertEqual(self.engine.get_observation()[0][:3], [CellState.HIDDEN, CellState.FLAGGED, CellState.FLAGGED])
        count = len(self.ui._replay_recorder.events)
        old_callback()
        self.assertEqual(len(self.ui._replay_recorder.events), count)
        self.assertIsNone(self.ui._v1_pending)
        self.assertEqual(len(job.acks), 1)
        self.assertFalse(self.ui.allow_guess_checkbox.isChecked())
        job.complete_cancel()
        self.ui.simple_auto_checkbox.setChecked(True)
        adopted = job.requests[-1]
        self.assertEqual((adopted.input_seq, adopted.review_inputs, adopted.initial_flag_count), (0, 0, 2))
        fresh_review = plan_snapshot(adopted)
        self.assertEqual(fresh_review.review.flags, ((1, 0), (2, 0)))

    def test_old_timeout_cannot_consume_new_owner_or_rearmed_pending(self):
        from live_policy import plan_snapshot
        job = self.start()
        first = plan_snapshot(job.requests[-1])
        job.deliver(first)
        old_owner_callback = self.ui._simple_auto_timeout_slot
        self.ui.on_right_click(3, 4)
        job.complete_cancel()
        self.ui.simple_auto_checkbox.setChecked(True)
        second = plan_snapshot(job.requests[-1])
        job.deliver(second)
        old_rate_callback = self.ui._simple_auto_timeout_slot
        self.ui.simple_auto_interval_spin.setValue(500)
        reservation = self.ui._v1_timer_reservation
        with patch.object(self.engine, "step", wraps=self.engine.step) as step:
            old_owner_callback()
            old_rate_callback()
            step.assert_not_called()
            self.assertEqual(self.ui._v1_timer_reservation, reservation)
            self.assertIs(self.ui._v1_pending, second)
            self.assertTrue(self.ui._simple_auto_timer.isActive())
            self.tick()
        step.assert_called_once_with(3, 4, Action.FLAG)
        self.assertEqual(job.applied, [second.token])

    def test_cleanup_blocked_survives_new_game_and_manual_stays_available(self):
        job = self.start()
        self.ui.on_right_click(2, 2)
        job.complete_cancel(cleanup=False)
        self.assertIs(self.ui._v1_job, job)
        self.ui.on_reset()
        self.ui.on_right_click(3, 3)
        self.ui.simple_auto_checkbox.setChecked(True)
        self.ui.on_analyze_current()
        self.assertEqual(len(job.requests), 1)
        self.assertEqual(job.state, "blocked")
        self.assertIs(self.ui._v1_job, job)
        self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
        self.assertEqual(self.engine.get_observation()[3][3], CellState.FLAGGED)
        self.assertEqual(len(self.ui._replay_recorder.events), 1)

    def test_manual_flag_unflag_all_hidden_and_large_revision_adopts_without_canonical(self):
        from live_policy import ADOPT_CURRENT, plan_snapshot
        self.ui.on_right_click(6, 7)
        self.ui._live_action_count = 600  # Named accumulated-history boundary.
        self.ui.on_right_click(6, 7)
        job = self.start()
        snapshot = job.requests[-1]
        self.assertEqual((snapshot.entry_mode, snapshot.input_seq, snapshot.input_revision,
                          snapshot.cursor), (ADOPT_CURRENT, 0, 601, (6, 7)))
        proposal = plan_snapshot(snapshot)
        self.assertTrue(proposal.is_guess)
        self.assertFalse(proposal.initial)
        job.deliver(proposal)
        self.tick()
        self.assertEqual(len(self.ui._replay_recorder.events), 2)
        self.assertEqual(job.applied, [])

    def test_uncertain_ack_cannot_restart_through_policy_switch(self):
        job, _ = self.prepare_chord()
        job.ack_error = RuntimeError("synthetic ACK loss")
        self.tick()
        count = len(self.ui._replay_recorder.events)
        job.complete_cancel()
        self.ui.live_policy_combo.setCurrentIndex(0)
        self.ui.simple_auto_checkbox.setChecked(True)
        self.tick()
        self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
        self.assertEqual(len(self.ui._replay_recorder.events), count)
        self.assertTrue(self.ui._live_input_uncertain)

    def test_terminal_failure_prefix_does_not_match_nested_transport_text(self):
        with self.terminal_fixture(GameStatus.WON) as job:
            job.active_run_id, job.state = None, "idle"
            self.ui._on_v1_finished({"run_id": self.ui._live_run_id, "status": "FAILED",
                                     "cleanup_complete": True,
                                     "error": "REPLY_TRANSPORT: WORKER FINISH_EXIT_TIMEOUT: fake"})
            self.assertIn("WON · worker 실패", self.ui.live_policy_status_label.text())
            self.assertNotIn("worker 종료 지연", self.ui.live_policy_status_label.text())

    def test_retired_same_run_failure_still_blocks_auto_after_simple_selection(self):
        job = self.start()
        run_id = self.ui._live_run_id
        self.ui.on_right_click(3, 3)
        self.ui.live_policy_combo.setCurrentIndex(0)
        before = (self.engine.get_observation(), self.ui._replay_recorder.events,
                  self.ui._replay_recorder.source_type)
        job.active_run_id, job.state = None, "idle"
        record = {"run_id": run_id, "status": "CANCELLED", "cleanup_complete": True,
                  "error": "REPLY_TRANSPORT: unexpected failure before retirement"}
        self.ui._on_v1_finished(record)
        self.assertEqual(self.ui.live_owner_records[-1]["cleanup"], record)
        self.assertIn("이전 Auto 오류", self.ui.analysis_status_label.text())
        self.assertFalse(self.ui.simple_auto_checkbox.isEnabled())
        self.ui.simple_auto_checkbox.setChecked(True)
        self.tick()
        self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
        self.assertEqual(before, (self.engine.get_observation(), self.ui._replay_recorder.events,
                                  self.ui._replay_recorder.source_type))
        self.assertEqual(len(job.requests), 1)

    def test_selector_clears_auto_pending_and_overlay_before_cancelling_owner(self):
        from live_policy import plan_snapshot
        job = self.start()
        proposal = plan_snapshot(job.requests[-1])
        job.deliver(proposal)
        generation = self.ui._live_board_generation
        before = (self.engine.get_observation(), self.ui._replay_recorder.events)
        cancel = job.cancel

        def inspect_cancel(reason):
            self.assertGreater(self.ui._live_board_generation, generation)
            self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
            self.assertIsNone(self.ui._v1_pending)
            self.assertIsNone(self.ui._v1_timer_reservation)
            self.assertIsNone(self.ui._analysis_result)
            self.assertTrue(all(cell.analysis_overlay is None for cell in self.ui._buttons.values()))
            self.assertEqual(self.ui._mouse_buttons, Qt.NoButton)
            cancel(reason)

        with patch.object(job, "cancel", side_effect=inspect_cancel) as retiring:
            self.ui.live_policy_combo.setCurrentIndex(0)
        retiring.assert_called_once_with("Auto 정책 변경")
        self.assertEqual(before, (self.engine.get_observation(), self.ui._replay_recorder.events))
        self.assertEqual(len(job.requests), 1)

if __name__ == "__main__":
    unittest.main()
