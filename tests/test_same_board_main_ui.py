"""Offscreen main-window source capture and Comparison ownership integration."""

import builtins
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
import os
from pathlib import Path
import shutil
import unittest
from unittest.mock import Mock, patch

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from qt_bootstrap import configure_qt_plugin_path

configure_qt_plugin_path()
try:
    from PyQt5.QtCore import QObject, pyqtSignal
    from PyQt5.QtGui import QCloseEvent
    from PyQt5.QtWidgets import QApplication
except ImportError:
    QApplication = None
else:
    import same_board_comparison_launcher as launcher_module
    from core_engine import Action, GameStatus, MinesweeperEngine
    from replay_model import ReplayBoard, ReplayData, ReplayEvent, SOURCE_ALGORITHM, SOURCE_AI
    from replay_player import ReplayPlayer
    from same_board_comparison import HumanComparisonContext
    from same_board_execution_job import SameBoardExecutionJob
    from tests.test_same_board_runner import human_context
    from tests.ui_settings import isolate_ui_settings
    from ui_manager import MinesweeperUI

    class MainComparisonJob(QObject):
        succeeded = pyqtSignal(object, object)
        failed = pyqtSignal(object, str)
        cancelled = pyqtSignal(object)

        def __init__(self, parent=None):
            super().__init__(parent)
            self.state = "idle"
            self.started = []
            self.shutdown_calls = 0
            self.shutdown_error = None

        def start(self, context):
            self.started.append(context)
            self.state = "running"
            return len(self.started)

        def cancel(self):
            self.state = "cancelling"

        def shutdown(self):
            self.shutdown_calls += 1
            if self.shutdown_error is not None:
                raise self.shutdown_error
            self.state = "idle"


@unittest.skipIf(QApplication is None, "PyQt5 unavailable")
class SameBoardMainUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.settings = isolate_ui_settings(self)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(MinesweeperUI, "_ensure_zini_metric_job"))
        self.stack.enter_context(patch.object(launcher_module, "SameBoardExecutionJob", MainComparisonJob))
        self.information = self.stack.enter_context(patch("ui_manager.QMessageBox.information"))
        self.warning = self.stack.enter_context(patch("ui_manager.QMessageBox.warning"))
        self.ui = MinesweeperUI(MinesweeperEngine(4, 1, 1))
        self.addCleanup(self.close_ui)

    def close_ui(self):
        owner = self.ui._same_board_comparison_launcher
        if owner is not None and owner.job is not None and isinstance(owner.job, MainComparisonJob):
            owner.job.shutdown_error = None
        self.ui._stop_timer()
        self.ui._stop_replay_autoplay()
        self.ui.close()
        self.ui.deleteLater()
        self.app.processEvents()

    def enter_replay(self, replay=None, index=0):
        replay = human_context().human_replay if replay is None else replay
        player = ReplayPlayer(replay)
        player.go_to(index)
        self.ui._enter_replay_mode(player)
        return replay

    def complete_live(self):
        self.ui.engine.reset_with_mines(4, 1, 1, {(1, 0)})
        self.ui._reset_replay_recorder()
        for x in (0, 2, 3):
            self.ui._apply_live_action(x, 0, Action.OPEN)
        self.assertEqual(self.ui.engine.status, GameStatus.WON)

    def open_comparison(self):
        self.ui.on_same_board_comparison()
        self.assertIsNotNone(self.ui._same_board_comparison_launcher)
        return self.ui._same_board_comparison_launcher

    def messages(self):
        return "\n".join(str(value) for mock in (self.information, self.warning)
                         for call in mock.call_args_list for value in call.args[1:])

    def assert_rejected(self, reason):
        self.ui.on_same_board_comparison()
        self.assertIsNone(self.ui._same_board_comparison_launcher)
        self.assertIn("Cannot use this Replay for Same-board Comparison", self.messages())
        self.assertIn(reason, self.messages())

    def snapshot_source(self):
        main = self.ui
        player = main._replay_player
        return (
            id(main.engine), main.engine.get_board_snapshot(),
            deepcopy(main.engine.get_observation()), main.engine.status,
            main._replay_mode, id(main._replay_data), id(player),
            None if player is None else player.current_index,
            None if player is None else deepcopy(player.get_observation()),
            id(main._mouse_trace_recorder), tuple(main._replay_recorder.events),
            main.difficulty_combo.currentIndex(), main._normal_game_config,
            tuple((name, item.text()) for name, item in main._stat_value_items.items()),
        )

    def test_tools_action_exists_once_and_initial_source_is_unavailable(self):
        action = self.ui.same_board_comparison_action
        self.assertEqual(self.ui.tools_button.menu().actions().count(action), 1)
        self.assertEqual(action.text(), "Compare as full-game Human Replay…")
        self.assertFalse(action.isEnabled())
        for text in (action.toolTip(), action.statusTip()):
            self.assertIn("Finish the current game or load a full-game Human Replay.", text)
        self.assertIsNone(self.ui._same_board_comparison_launcher)

    def test_main_initialization_keeps_comparison_imports_lazy(self):
        real_import = builtins.__import__

        def guarded(name, *args, **kwargs):
            if name in ("same_board_comparison_launcher", "same_board_execution_job", "same_board_comparison"):
                raise AssertionError("Comparison construction must remain lazy")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=guarded):
            other = MinesweeperUI(MinesweeperEngine(3, 3, 1))
            try:
                self.assertIsNone(other._same_board_comparison_launcher)
            finally:
                other.close()
                other.deleteLater()

    def test_completed_live_enables_action_without_automatic_declaration(self):
        with patch("same_board_comparison.HumanComparisonContext", wraps=HumanComparisonContext) as admit:
            self.complete_live()
            self.assertTrue(self.ui.same_board_comparison_action.isEnabled())
            self.assertIsNone(self.ui._same_board_comparison_launcher)
            admit.assert_not_called()
            self.ui.on_reset()
            self.assertFalse(self.ui.same_board_comparison_action.isEnabled())

    def test_placed_unfinished_live_and_direct_unavailable_call_are_safe(self):
        self.ui.engine.reset_with_mines(4, 1, 1, {(1, 0)})
        self.ui._update_same_board_comparison_action()
        self.assertFalse(self.ui.same_board_comparison_action.isEnabled())
        self.ui.on_same_board_comparison()
        self.assertIsNone(self.ui._same_board_comparison_launcher)
        self.assertTrue(self.messages())

    def test_replay_eligibility_tracks_metadata_and_exit(self):
        replay = self.enter_replay()
        self.assertTrue(self.ui.same_board_comparison_action.isEnabled())
        for source in (SOURCE_ALGORITHM, SOURCE_AI):
            with self.subTest(source=source):
                self.enter_replay(replace(replay, source_type=source))
                action = self.ui.same_board_comparison_action
                self.assertFalse(action.isEnabled())
                self.assertIn("requires a Human-labeled Replay", action.toolTip())
                self.assertIn("requires a Human-labeled Replay", action.statusTip())
        self.enter_replay(replay)
        self.assertTrue(self.ui.same_board_comparison_action.isEnabled())
        self.ui._exit_replay_mode()
        self.assertFalse(self.ui.same_board_comparison_action.isEnabled())

    def test_explicit_action_reuses_builder_and_declares_once(self):
        replay = self.enter_replay()
        with patch.object(self.ui, "_build_current_replay_data", wraps=self.ui._build_current_replay_data) as build, \
                patch("same_board_comparison.HumanComparisonContext", wraps=HumanComparisonContext) as admit:
            self.ui.same_board_comparison_action.trigger()
            build.assert_called_once_with("Same-board Comparison", require_finished=True, allow_replay_mode=True)
            admit.assert_called_once_with(replay, declared_full_game_human=True)
        owner = self.ui._same_board_comparison_launcher
        self.assertIs(owner.context.human_replay, replay)
        self.assertEqual(owner.job.started, [])

    def test_live_capture_uses_current_recorder_and_preserves_optional_trace(self):
        self.complete_live()
        trace = human_context(with_trace=True).human_replay.mouse_trace
        built = []
        original = self.ui._build_current_replay_data

        def capture(*args, **kwargs):
            replay = original(*args, **kwargs)
            built.append(replay)
            return replay

        before = self.snapshot_source()
        with patch.object(self.ui._mouse_trace_recorder, "snapshot", return_value=trace), \
                patch.object(self.ui, "_build_current_replay_data", side_effect=capture), \
                patch.object(launcher_module, "SameBoardComparisonLauncherWindow",
                             wraps=launcher_module.SameBoardComparisonLauncherWindow) as factory:
            owner = self.open_comparison()
        self.assertIs(owner.context.human_replay, built[0])
        self.assertEqual(built[0].events, self.ui._replay_recorder.events)
        self.assertIs(built[0].mouse_trace, trace)
        self.assertEqual(factory.call_args.kwargs["source_description"], "completed current game")
        self.assertEqual(self.snapshot_source(), before)

    def test_replay_capture_uses_whole_original_at_zero_middle_and_final(self):
        replay = human_context(with_trace=True).human_replay
        for index in (0, 1, len(replay.events)):
            with self.subTest(index=index):
                self.enter_replay(replay, index)
                before = self.snapshot_source()
                with patch.object(launcher_module, "SameBoardComparisonLauncherWindow",
                                  wraps=launcher_module.SameBoardComparisonLauncherWindow) as factory, \
                        patch("ui_manager.QFileDialog.getOpenFileName", side_effect=AssertionError("new loader")):
                    owner = self.open_comparison()
                self.assertIs(owner.context.human_replay, replay)
                self.assertIs(owner.context.human_replay.mouse_trace, replay.mouse_trace)
                self.assertEqual(len(owner.context.human_replay.events), len(replay.events))
                self.assertEqual(factory.call_args.kwargs["source_description"], "currently loaded Replay")
                self.assertEqual(self.snapshot_source(), before)
                self.assertTrue(owner.close())

    def test_replay_source_takes_precedence_over_completed_live_game(self):
        self.complete_live()
        replay = self.enter_replay(human_context(mined_origin=True).human_replay)
        owner = self.open_comparison()
        self.assertIs(owner.context.human_replay, replay)
        self.assertNotEqual(owner.context.layout.board.width, self.ui.engine.width)

    def test_incomplete_human_replay_is_enabled_then_precisely_rejected(self):
        replay = human_context().human_replay
        replay = replace(replay, events=replay.events[:1])
        self.enter_replay(replay)
        before = self.snapshot_source()
        self.assertTrue(self.ui.same_board_comparison_action.isEnabled())
        self.assert_rejected("incomplete")
        self.assertEqual(self.snapshot_source(), before)
        self.ui.on_replay_next()
        self.assertEqual(self.ui._replay_player.current_index, 1)

    def test_post_terminal_replay_receives_comparison_reason_without_mutation(self):
        replay = human_context().human_replay
        replay = replace(replay, events=replay.events + (ReplayEvent(30, 0, 0, "OPEN"),))
        self.enter_replay(replay)
        before = self.snapshot_source()
        self.assert_rejected("follows terminal event")
        self.assertEqual(self.snapshot_source(), before)
        self.ui.on_replay_last()
        self.assertEqual(self.ui._replay_player.current_index, len(replay.events))

    def test_unsupported_dimensions_receive_comparison_reason(self):
        replay = ReplayData(ReplayBoard(31, 1, 1, {(0, 0)}), (ReplayEvent(0, 0, 0, "OPEN"),))
        self.enter_replay(replay)
        self.assertTrue(self.ui.same_board_comparison_action.isEnabled())
        before = self.snapshot_source()
        self.assert_rejected("width 1..30")
        self.assertEqual(self.snapshot_source(), before)

    def test_direct_slot_cannot_override_algorithm_or_ai_metadata(self):
        for source in (SOURCE_ALGORITHM, SOURCE_AI):
            with self.subTest(source=source):
                replay = replace(human_context().human_replay, source_type=source)
                self.enter_replay(replay)
                before = self.snapshot_source()
                self.assertFalse(self.ui.same_board_comparison_action.isEnabled())
                self.assert_rejected("SOURCE_HUMAN")
                self.assertIs(self.ui._replay_data, replay)
                self.assertEqual(self.snapshot_source(), before)

    def test_mined_origin_without_mouse_trace_is_eligible(self):
        replay = self.enter_replay(human_context(mined_origin=True).human_replay)
        owner = self.open_comparison()
        self.assertIs(owner.context.human_replay, replay)
        self.assertTrue(owner.context.solver_origin_is_mine)
        self.assertIsNone(replay.mouse_trace)
        self.assertEqual(owner.job.started, [])

    def test_source_and_launcher_construction_failures_stay_in_slot(self):
        self.enter_replay()
        with patch.object(self.ui, "_build_current_replay_data", side_effect=RuntimeError("capture unavailable")):
            self.assert_rejected("capture unavailable")
        with patch.object(launcher_module, "SameBoardComparisonLauncherWindow", side_effect=RuntimeError("window unavailable")):
            self.assert_rejected("window unavailable")

    def test_existing_launcher_only_raises_and_never_recaptures(self):
        self.enter_replay()
        owner = self.open_comparison()
        context = owner.context
        self.ui._exit_replay_mode()
        action = self.ui.same_board_comparison_action
        self.assertEqual(action.text(), "Open Comparison…")
        self.assertTrue(action.isEnabled())
        with patch.object(self.ui, "_build_current_replay_data", side_effect=AssertionError("recapture")), \
                patch("same_board_comparison.HumanComparisonContext", side_effect=AssertionError("readmission")), \
                patch.object(launcher_module, "SameBoardComparisonLauncherWindow", side_effect=AssertionError("second launcher")), \
                patch.object(owner, "show") as show, patch.object(owner, "raise_") as raise_window, \
                patch.object(owner, "activateWindow") as activate:
            action.trigger()
        show.assert_called_once_with()
        raise_window.assert_called_once_with()
        activate.assert_called_once_with()
        self.assertIs(owner.context, context)
        self.assertEqual(owner.job.started, [])

    def test_captured_context_survives_all_main_source_changes(self):
        original = self.enter_replay(human_context(with_trace=True).human_replay)
        owner = self.open_comparison()
        context = owner.context
        self.ui.on_replay_next()
        self.ui._exit_replay_mode()
        self.ui.on_reset()
        self.ui._rebuild_game(5, 5, 3)
        self.ui.engine.reset_with_mines(5, 5, 3, {(1, 1), (3, 1), (3, 3)})
        self.ui._apply_live_action(0, 0, Action.OPEN)
        self.enter_replay(human_context(mined_origin=True).human_replay)
        self.assertIs(owner.context, context)
        self.assertIs(owner.context.human_replay, original)
        self.assertIs(owner.context.human_replay.mouse_trace, original.mouse_trace)
        self.assertEqual(owner.job.started, [])

    def test_launcher_close_recalculates_current_source_and_ignores_old_sender(self):
        replay = self.enter_replay()
        old = self.open_comparison()
        self.enter_replay(replace(replay, source_type=SOURCE_AI))
        self.assertTrue(old.close())
        self.assertIsNone(self.ui._same_board_comparison_launcher)
        self.assertEqual(self.ui.same_board_comparison_action.text(), "Compare as full-game Human Replay…")
        self.assertFalse(self.ui.same_board_comparison_action.isEnabled())
        self.enter_replay(replay)
        new = self.open_comparison()
        old.closed.emit()
        self.assertIs(self.ui._same_board_comparison_launcher, new)

    def test_live_new_game_recalculates_action_eligibility(self):
        self.complete_live()
        self.assertTrue(self.ui.same_board_comparison_action.isEnabled())
        self.ui._rebuild_game(5, 5, 3)
        self.assertFalse(self.ui.same_board_comparison_action.isEnabled())

    def test_opening_comparison_does_not_call_producers_or_main_navigation(self):
        self.enter_replay(human_context(with_trace=True).human_replay, 1)
        with ExitStack() as guards:
            for path in ("same_board_runner.run_same_board_comparison", "simple_runner.run_simple",
                         "stage3_runner.run_stage3", "stage3_planner.plan_position",
                         "benchmark_modeled_time.authenticate_model_c", "benchmark_board.generate_board"):
                guards.enter_context(patch(path, side_effect=AssertionError(path)))
            for name in ("_enter_replay_mode", "_exit_replay_mode", "on_reset", "_rebuild_game"):
                guards.enter_context(patch.object(self.ui, name, side_effect=AssertionError(name)))
            owner = self.open_comparison()
        self.assertEqual(owner.job.started, [])
        self.assertEqual(self.ui._replay_player.current_index, 1)

    def test_main_close_orders_comparison_before_stage3_then_remaining_cleanup(self):
        self.enter_replay()
        owner = self.open_comparison()
        owner.run_button.click()
        job = owner.job
        order = []
        stage3 = Mock()
        stage3.close.side_effect = lambda: order.append("stage3") or True
        self.ui._stage3_visualizer_launcher = stage3
        statistics = Mock()
        self.ui._benchmark_statistics_window = statistics
        original_shutdown = job.shutdown

        def shutdown():
            order.append("comparison")
            original_shutdown()

        with patch.object(job, "shutdown", side_effect=shutdown), \
                patch.object(self.ui, "_invalidate_mouse_input", side_effect=lambda: order.append("main")), \
                patch.object(self.ui, "_stop_simple_auto") as stop_auto, \
                patch.object(self.ui, "_reset_zini_metric_job") as stop_zini:
            event = QCloseEvent()
            self.ui.closeEvent(event)
            self.assertTrue(event.isAccepted())
        self.assertEqual(order, ["comparison", "stage3", "main"])
        self.assertEqual(job.state, "idle")
        self.assertIsNone(self.ui._same_board_comparison_launcher)
        statistics.close.assert_called_once_with()
        stop_auto.assert_called_once_with()
        stop_zini.assert_called_once_with()
        self.ui._stage3_visualizer_launcher = None
        self.ui._benchmark_statistics_window = None

    def test_comparison_close_failure_stops_later_teardown_and_retry_can_succeed(self):
        self.enter_replay()
        owner = self.open_comparison()
        owner.run_button.click()
        job = owner.job
        job.shutdown_error = RuntimeError("child still owned")
        stage3 = Mock()
        stage3.close.return_value = True
        self.ui._stage3_visualizer_launcher = stage3
        statistics = Mock()
        self.ui._benchmark_statistics_window = statistics
        with patch.object(self.ui, "_invalidate_mouse_input") as invalidate, \
                patch.object(self.ui, "_stop_simple_auto") as stop_auto, \
                patch.object(self.ui, "_reset_zini_metric_job") as stop_zini, \
                patch.object(self.ui._mouse_trace_recorder, "freeze") as freeze:
            event = QCloseEvent()
            self.ui.closeEvent(event)
            self.assertFalse(event.isAccepted())
            for operation in (invalidate, stop_auto, stop_zini, freeze, stage3.close, statistics.close):
                operation.assert_not_called()
            self.assertIs(self.ui._same_board_comparison_launcher, owner)
            self.assertIs(owner.job, job)
            job.shutdown_error = None
            event = QCloseEvent()
            self.ui.closeEvent(event)
            self.assertTrue(event.isAccepted())
        self.assertEqual(job.shutdown_calls, 2)
        stage3.close.assert_called_once_with()
        self.assertIsNone(self.ui._same_board_comparison_launcher)
        self.ui._stage3_visualizer_launcher = None
        self.ui._benchmark_statistics_window = None

    def test_existing_stage3_rejection_still_blocks_remaining_main_teardown(self):
        self.enter_replay()
        owner = self.open_comparison()
        stage3 = Mock()
        stage3.close.return_value = False
        self.ui._stage3_visualizer_launcher = stage3
        with patch.object(self.ui, "_invalidate_mouse_input") as invalidate:
            event = QCloseEvent()
            self.ui.closeEvent(event)
            self.assertFalse(event.isAccepted())
            invalidate.assert_not_called()
        self.assertTrue(owner._closed)
        self.assertIsNone(self.ui._same_board_comparison_launcher)
        self.assertIs(self.ui._stage3_visualizer_launcher, stage3)
        self.ui._stage3_visualizer_launcher = None

    def test_main_close_reaps_actual_owned_job_before_removing_directory(self):
        self.enter_replay()
        with patch.object(launcher_module, "SameBoardExecutionJob", SameBoardExecutionJob):
            owner = self.open_comparison()
        job = owner.job
        process = Mock()
        process.poll.return_value = None
        process.wait.return_value = 0
        with patch("same_board_execution_job.subprocess.Popen", return_value=process):
            owner.run_button.click()
        directory = Path(job._job_dir)
        self.assertTrue(directory.is_dir())
        self.assertIs(job._context, owner.context)
        process.wait.assert_not_called()
        real_remove = shutil.rmtree
        with patch("same_board_execution_job.shutil.rmtree") as cleanup:
            def reaped_before_cleanup(path):
                self.assertIsNone(job._process)
                process.wait.assert_called_once_with(timeout=0.5)
                return real_remove(path)

            cleanup.side_effect = reaped_before_cleanup
            self.assertTrue(self.ui.close())
        process.terminate.assert_called_once_with()
        self.assertIsNone(job._process)
        self.assertIsNone(job._job_dir)
        self.assertFalse(directory.exists())
        self.assertIsNone(self.ui._same_board_comparison_launcher)


if __name__ == "__main__":
    unittest.main()
