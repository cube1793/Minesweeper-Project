"""Offscreen launcher ownership tests using recorded traces and a fake job."""

from contextlib import ExitStack
import os
import unittest
from unittest.mock import patch

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from qt_bootstrap import configure_qt_plugin_path

configure_qt_plugin_path()
try:
    from PyQt5.QtCore import QEvent, QObject, Qt, pyqtSignal
    from PyQt5.QtGui import QCloseEvent
    from PyQt5.QtTest import QSignalSpy
    from PyQt5.QtWidgets import QApplication, QWidget
except ImportError:
    QApplication = None
else:
    import stage3_visualizer_launcher as launcher
    from stage3_visualizer_ui import Stage3VisualizerWindow
    from tests.test_stage3_visualizer_ui import execution_fixture


if QApplication is not None:
    class FakeStage3ExecutionJob(QObject):
        succeeded = pyqtSignal(object, object)
        failed = pyqtSignal(object, str)
        cancelled = pyqtSignal(object)

        def __init__(self, parent=None):
            super().__init__(parent)
            self.state = "idle"
            self.started = []
            self.cancel_calls = 0
            self.shutdown_calls = 0
            self.shutdown_error = None
            self.shutdown_hook = None
            self.start_error = None
            self.cancel_hook = None

        def start(self, game_index):
            if self.start_error is not None:
                raise self.start_error
            if self.state != "idle":
                raise RuntimeError("job is busy")
            token = len(self.started) + 1
            self.started.append((token, game_index))
            self.state = "running"
            return token

        def cancel(self):
            self.cancel_calls += 1
            self.state = "cancelling"
            if self.cancel_hook is not None:
                self.cancel_hook()

        def shutdown(self):
            self.shutdown_calls += 1
            if self.shutdown_hook is not None:
                self.shutdown_hook()
            if self.shutdown_error is not None:
                self.state = "cancelling"
                raise self.shutdown_error
            self.state = "idle"

        def finish_success(self, execution):
            self.state = "idle"
            self.succeeded.emit(self.started[-1][0], execution)

        def finish_failure(self, diagnostic="worker failed"):
            self.state = "idle"
            self.failed.emit(self.started[-1][0], diagnostic)

        def finish_cancel(self):
            self.state = "idle"
            self.cancelled.emit(self.started[-1][0])


@unittest.skipIf(QApplication is None, "PyQt5 unavailable")
class Stage3LauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(launcher, "Stage3ExecutionJob", FakeStage3ExecutionJob))
        self.viewer_factory = self.stack.enter_context(
            patch.object(launcher, "Stage3VisualizerWindow", wraps=Stage3VisualizerWindow)
        )
        for producer in (
            "stage3_execution.run_expert_stage3_execution", "stage3_execution.run_stage3",
            "stage3_execution.generate_board", "stage3_runner.run_stage3",
            "stage3_runner.plan_position", "stage3_planner.plan_position",
            "benchmark_board.generate_board",
        ):
            self.stack.enter_context(patch(producer, side_effect=AssertionError(producer)))
        self.execution = execution_fixture()
        self.window = launcher.Stage3VisualizerLauncherWindow()
        self.job = self.window.job
        self.addCleanup(self.close_window)

    def close_window(self):
        self.job.shutdown_error = None
        self.job.shutdown_hook = None
        self.window.close()
        self.app.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()

    def start_request(self, game_index="0"):
        self.window.game_index_edit.setText(game_index)
        self.window.run_button.click()
        return self.window._active_token

    def complete_request(self):
        self.start_request()
        self.job.finish_success(self.execution)
        return self.window._visualizer_window

    def assert_idle_controls(self):
        self.assertIsNone(self.window._active_token)
        self.assertTrue(self.window.game_index_edit.isEnabled())
        self.assertTrue(self.window.run_button.isEnabled())
        self.assertFalse(self.window.cancel_button.isEnabled())

    def test_fixed_identity_default_and_top_level_ownership(self):
        window = self.window
        self.assertEqual(window.windowTitle(), "Stage-3 Visualizer 실행")
        self.assertEqual(window.windowType(), Qt.Window)
        self.assertTrue(window.testAttribute(Qt.WA_DeleteOnClose))
        self.assertEqual(window.benchmark_label.text(), "Benchmark: EXPERT_GENERAL_V1")
        self.assertEqual(window.algorithm_label.text(), "Algorithm: Stage-3 V1 / Model C")
        self.assertEqual(window.game_index_edit.text(), "0")
        self.assertIs(self.job.parent(), window)
        self.assert_idle_controls()
        self.assertFalse(window.open_result_button.isEnabled())
        self.assertEqual(self.job.started, [])

    def test_invalid_input_never_starts_a_job(self):
        for text in ("", " ", "-1", "1.0", "1e3", "True", "+1", "0x10", "1_000", "１２"):
            with self.subTest(text=text):
                self.start_request(text)
                self.assertEqual(self.job.started, [])
                self.assertIn("0 이상의 정수", self.window.status_label.text())
                self.assert_idle_controls()

    def test_accepts_nonnegative_decimal_python_integers_without_prefix_cap(self):
        for text, expected in (("0", 0), ("0007", 7), ("100000", 100000), (str(2**128), 2**128)):
            with self.subTest(text=text):
                self.start_request(text)
                self.assertEqual(self.job.started[-1][1], expected)
                self.job.finish_cancel()

    def test_run_blocks_input_duplicate_start_and_enables_cancel(self):
        token = self.start_request("42")
        self.assertEqual(token, 1)
        self.assertEqual(self.job.started, [(1, 42)])
        self.assertFalse(self.window.game_index_edit.isEnabled())
        self.assertFalse(self.window.run_button.isEnabled())
        self.assertTrue(self.window.cancel_button.isEnabled())
        self.assertFalse(self.window.open_result_button.isEnabled())
        self.assertIn("실행 중", self.window.status_label.text())
        self.assertIn("42", self.window.status_label.text())
        self.window.on_run()
        self.window.game_index_edit.returnPressed.emit()
        self.assertEqual(self.job.started, [(1, 42)])

    def test_cancel_blocks_new_run_until_completion_and_is_idempotent(self):
        token = self.start_request()
        self.window.cancel_button.click()
        self.assertEqual(self.job.cancel_calls, 1)
        self.assertEqual(self.window._active_token, token)
        self.assertEqual(self.job.state, "cancelling")
        self.assertIn("취소 중", self.window.status_label.text())
        self.assertFalse(self.window.cancel_button.isEnabled())
        self.assertFalse(self.window.run_button.isEnabled())
        self.assertFalse(self.window.game_index_edit.isEnabled())
        self.window.on_cancel()
        self.window.on_run()
        self.assertEqual(self.job.cancel_calls, 1)
        self.assertEqual(len(self.job.started), 1)
        self.job.finish_cancel()
        self.assert_idle_controls()
        self.assertIsNone(self.window._completed_execution)
        self.viewer_factory.assert_not_called()
        self.start_request("2")
        self.assertEqual(self.job.started, [(1, 0), (2, 2)])

    def test_cancel_intent_wins_over_matching_success_during_cancel_call(self):
        token = self.start_request()
        self.job.cancel_hook = lambda: self.job.succeeded.emit(token, self.execution)
        self.window.on_cancel()
        self.assertEqual(self.window._active_token, token)
        self.assertIsNone(self.window._completed_execution)
        self.viewer_factory.assert_not_called()
        self.assertFalse(self.window.run_button.isEnabled())
        self.job.finish_cancel()
        self.job.succeeded.emit(token, self.execution)
        self.assert_idle_controls()
        self.viewer_factory.assert_not_called()

    def test_success_retains_execution_and_opens_one_viewer(self):
        viewer = self.complete_request()
        self.assertIs(self.window._completed_execution, self.execution)
        self.assertIs(viewer.player.execution, self.execution)
        self.assertIs(viewer.parent(), self.window)
        self.assertTrue(viewer.isVisible())
        self.assert_idle_controls()
        self.assertTrue(self.window.open_result_button.isEnabled())
        self.assertIn("완료", self.window.status_label.text())
        self.assertIn(self.execution.result.status.name, self.window.status_label.text())
        self.viewer_factory.assert_called_once_with(self.execution, self.window)

    def test_close_viewer_reopens_retained_result_without_rerun(self):
        viewer = self.complete_request()
        self.assertTrue(viewer.close())
        self.assertIsNone(self.window._visualizer_window)
        self.assertIs(self.window._completed_execution, self.execution)
        self.assertFalse(self.window._closed)
        self.window.open_result_button.click()
        reopened = self.window._visualizer_window
        self.assertIsNot(reopened, viewer)
        self.assertIs(reopened.player.execution, self.execution)
        self.assertEqual(self.viewer_factory.call_count, 2)
        self.assertEqual(self.job.started, [(1, 0)])

    def test_repeated_open_raises_existing_viewer(self):
        viewer = self.complete_request()
        with patch.object(viewer, "show") as show, patch.object(viewer, "raise_") as raise_window, \
                patch.object(viewer, "activateWindow") as activate:
            for _ in range(3):
                self.window.open_result_button.click()
            self.assertEqual(show.call_count, 3)
            self.assertEqual(raise_window.call_count, 3)
            self.assertEqual(activate.call_count, 3)
        self.assertEqual(self.viewer_factory.call_count, 1)
        self.assertIs(self.window._visualizer_window, viewer)

    def test_new_run_closes_old_viewer_and_clears_completed_execution(self):
        viewer = self.complete_request()
        viewer.on_play_pause()
        self.start_request("9")
        self.assertTrue(viewer._closed)
        self.assertFalse(viewer.timer.isActive())
        self.assertIsNone(self.window._visualizer_window)
        self.assertIsNone(self.window._completed_execution)
        self.assertFalse(self.window.open_result_button.isEnabled())
        self.assertEqual(self.job.started, [(1, 0), (2, 9)])

    def test_invalid_new_input_preserves_previous_result_and_viewer(self):
        viewer = self.complete_request()
        self.start_request("-1")
        self.assertIs(self.window._visualizer_window, viewer)
        self.assertIs(self.window._completed_execution, self.execution)
        self.assertEqual(len(self.job.started), 1)

    def test_failure_shows_plain_diagnostic_without_opening_viewer(self):
        self.start_request()
        self.job.finish_failure("<worker error>")
        self.assert_idle_controls()
        self.assertIsNone(self.window._completed_execution)
        self.assertFalse(self.window.open_result_button.isEnabled())
        self.assertIn("<worker error>", self.window.status_label.text())
        self.assertEqual(self.window.status_label.textFormat(), Qt.PlainText)
        self.viewer_factory.assert_not_called()

    def test_cleanup_failure_keeps_run_blocked_until_final_shutdown(self):
        token = self.start_request()
        self.job.state = "cancelling"
        self.job.failed.emit(token, "cleanup failed")
        self.assertIsNone(self.window._active_token)
        self.assertFalse(self.window.run_button.isEnabled())
        self.assertFalse(self.window.game_index_edit.isEnabled())
        self.assertFalse(self.window.cancel_button.isEnabled())
        self.window.on_run()
        self.assertEqual(len(self.job.started), 1)
        self.assertTrue(self.window.close())
        self.assertEqual(self.job.shutdown_calls, 1)

    def test_stale_success_failure_and_cancellation_leave_current_request_untouched(self):
        old_token = self.start_request()
        self.job.finish_cancel()
        current_token = self.start_request("3")
        original_status = self.window.status_label.text()
        for token in (old_token, current_token + 1, True, float(current_token), None):
            with self.subTest(token=token):
                self.job.succeeded.emit(token, self.execution)
                self.job.failed.emit(token, "stale diagnostic")
                self.job.cancelled.emit(token)
                self.assertEqual(self.window._active_token, current_token)
                self.assertEqual(self.window.status_label.text(), original_status)
                self.assertIsNone(self.window._completed_execution)
                self.assertFalse(self.window.run_button.isEnabled())
                self.viewer_factory.assert_not_called()

    def test_terminal_duplicates_cannot_replace_retained_result_or_status(self):
        viewer = self.complete_request()
        original_status = self.window.status_label.text()
        token = self.job.started[-1][0]
        self.job.succeeded.emit(token, execution_fixture("loss"))
        self.job.failed.emit(token, "late failure")
        self.job.cancelled.emit(token)
        self.assertIs(self.window._completed_execution, self.execution)
        self.assertIs(self.window._visualizer_window, viewer)
        self.assertEqual(self.window.status_label.text(), original_status)
        self.assertEqual(self.viewer_factory.call_count, 1)

    def test_old_viewer_closed_signal_cannot_clear_new_viewer(self):
        old_viewer = self.complete_request()
        self.start_request("4")
        self.job.finish_success(self.execution)
        new_viewer = self.window._visualizer_window
        old_viewer.closed.emit()
        self.assertIs(self.window._visualizer_window, new_viewer)

    def test_close_active_job_shuts_down_and_publishes_closed_once(self):
        token = self.start_request()
        signal = QSignalSpy(self.window.closed)
        self.job.shutdown_hook = lambda: self.job.succeeded.emit(token, self.execution)
        self.assertTrue(self.window.close())
        self.assertEqual(self.job.shutdown_calls, 1)
        self.assertIsNone(self.window.job)
        self.assertIsNone(self.window._active_token)
        self.assertIsNone(self.window._completed_execution)
        self.assertIsNone(self.window._visualizer_window)
        self.assertTrue(self.window._closed)
        self.viewer_factory.assert_not_called()
        self.assertEqual(len(signal), 1)
        event = QCloseEvent()
        self.window.closeEvent(event)
        self.assertTrue(event.isAccepted())
        self.assertEqual(len(signal), 1)
        self.assertEqual(self.job.shutdown_calls, 1)
        self.job.succeeded.emit(token, self.execution)
        self.job.failed.emit(token, "late failure")
        self.job.cancelled.emit(token)
        self.window.on_run()
        self.window.on_cancel()
        self.window.on_open_result()
        self.viewer_factory.assert_not_called()
        self.assertEqual(len(self.job.started), 1)

    def test_close_launcher_closes_viewer_and_stops_playback(self):
        viewer = self.complete_request()
        viewer.on_play_pause()
        self.assertTrue(self.window.close())
        self.assertTrue(viewer._closed)
        self.assertFalse(viewer.timer.isActive())
        self.assertIsNone(self.window._visualizer_window)
        self.assertIsNone(self.window._completed_execution)
        self.assertEqual(self.job.shutdown_calls, 1)

    def test_shutdown_failure_rejects_close_retains_job_and_allows_close_retry(self):
        token = self.start_request()
        signal = QSignalSpy(self.window.closed)
        self.job.shutdown_error = RuntimeError("child not yet reaped")
        self.assertFalse(self.window.close())
        self.assertEqual(len(signal), 0)
        self.assertFalse(self.window._closed)
        self.assertFalse(self.window._closing)
        self.assertIs(self.window.job, self.job)
        self.assertEqual(self.window._active_token, token)
        self.assertIn("child not yet reaped", self.window.status_label.text())
        self.assertFalse(self.window.run_button.isEnabled())
        self.job.succeeded.emit(token, self.execution)
        self.viewer_factory.assert_not_called()
        self.job.shutdown_error = None
        self.assertTrue(self.window.close())
        self.assertEqual(self.job.shutdown_calls, 2)
        self.assertEqual(len(signal), 1)

    def test_ignored_parent_close_never_shuts_down_or_emits(self):
        self.start_request()
        signal = QSignalSpy(self.window.closed)
        event = QCloseEvent()
        with patch.object(QWidget, "closeEvent", side_effect=lambda event: event.ignore()):
            self.window.closeEvent(event)
        self.assertFalse(event.isAccepted())
        self.assertEqual(self.job.shutdown_calls, 0)
        self.assertEqual(len(signal), 0)
        self.assertFalse(self.window._closed)
        self.assertTrue(self.window.cancel_button.isEnabled())

    def test_start_exception_is_visible_and_recovers_controls(self):
        self.job.start_error = RuntimeError("startup refused")
        self.start_request()
        self.assert_idle_controls()
        self.assertIn("startup refused", self.window.status_label.text())
        self.assertIsNone(self.window._completed_execution)
        self.viewer_factory.assert_not_called()

    def test_viewer_construction_failure_preserves_result_for_retry(self):
        self.start_request()
        self.viewer_factory.side_effect = ValueError("viewer unavailable")
        self.job.finish_success(self.execution)
        self.assertIsNone(self.window._visualizer_window)
        self.assertIs(self.window._completed_execution, self.execution)
        self.assertTrue(self.window.open_result_button.isEnabled())
        self.assertIn("viewer unavailable", self.window.status_label.text())
        self.viewer_factory.side_effect = None
        self.window.open_result_button.click()
        self.assertIsNotNone(self.window._visualizer_window)
        self.assertEqual(len(self.job.started), 1)




# Main-window integration: real Qt windows, deterministic result, no solver.
import builtins as _main_builtins
from contextlib import ExitStack as _MainExitStack
from copy import deepcopy as _main_deepcopy
from unittest.mock import Mock as _MainMock, patch as _main_patch

try:
    from PyQt5.QtCore import QObject as _MainQObject, pyqtSignal as _main_signal
    from PyQt5.QtGui import QCloseEvent as _MainCloseEvent
    from PyQt5.QtWidgets import (
        QApplication as _MainQApplication, QPushButton as _MainPushButton,
        QToolButton as _MainToolButton,
    )
except ImportError:
    _MainQApplication = None
else:
    import stage3_visualizer_launcher as _main_launcher_module
    from core_engine import Action as _MainAction, MinesweeperEngine as _MainEngine
    from live_analysis import LiveAnalysis as _MainAnalysis, CellOverlay as _MainOverlay
    from replay_analysis import (
        ReplayStepAnalysis as _MainReplayAnalysis,
        ReplayComparisonKind as _MainReplayComparison,
    )
    from replay_model import (
        ReplayBoard as _MainReplayBoard, ReplayData as _MainReplayData,
        ReplayEvent as _MainReplayEvent,
    )
    from replay_player import ReplayPlayer as _MainReplayPlayer
    from tests.test_stage3_visualizer_ui import execution_fixture as _main_execution_fixture
    from tests.ui_settings import isolate_ui_settings as _main_isolate_settings
    from ui_manager import MinesweeperUI as _MainUI

    class _MainIntegrationFakeStage3Job(_MainQObject):
        succeeded = _main_signal(object, object)
        failed = _main_signal(object, str)
        cancelled = _main_signal(object)

        def __init__(self, parent=None):
            super().__init__(parent)
            self.state = "idle"
            self.token = 0
            self.started = []
            self.cancel_calls = 0
            self.shutdown_calls = 0
            self.shutdown_states = []
            self.shutdown_error = None

        def start(self, game_index):
            if self.state != "idle":
                raise RuntimeError("job is active")
            self.token += 1
            self.started.append(game_index)
            self.state = "running"
            return self.token

        def cancel(self):
            self.cancel_calls += 1
            self.state = "cancelling"

        def finish_success(self, execution):
            self.state = "idle"
            self.succeeded.emit(self.token, execution)

        def finish_cancel(self):
            self.state = "idle"
            self.cancelled.emit(self.token)

        def shutdown(self):
            self.shutdown_calls += 1
            self.shutdown_states.append(self.state)
            if self.shutdown_error is not None:
                raise self.shutdown_error
            self.state = "idle"


@unittest.skipIf(_MainQApplication is None, "PyQt5 unavailable")
class Stage3MainUIIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = _MainQApplication.instance() or _MainQApplication([])

    def setUp(self):
        self.settings = _main_isolate_settings(self)
        worker_patch = _main_patch.object(_MainUI, "_ensure_zini_metric_job")
        worker_patch.start()
        self.addCleanup(worker_patch.stop)
        job_patch = _main_patch.object(
            _main_launcher_module, "Stage3ExecutionJob", _MainIntegrationFakeStage3Job,
        )
        job_patch.start()
        self.addCleanup(job_patch.stop)
        self.engine = _MainEngine(3, 3, 1)
        self.ui = _MainUI(self.engine)
        self.addCleanup(self.close_ui)

    def close_ui(self):
        launcher = self.ui._stage3_visualizer_launcher
        if launcher is not None and launcher.job is not None:
            launcher.job.shutdown_error = None
        self.ui._stop_timer()
        self.ui._stop_replay_autoplay()
        self.ui.close()
        self.ui.deleteLater()
        self.app.processEvents()

    def open_launcher(self):
        self.ui.stage3_visualizer_button.click()
        launcher = self.ui._stage3_visualizer_launcher
        self.assertIsNotNone(launcher)
        return launcher

    def test_counters_entry_preserves_existing_tools_statistics_action(self):
        main = self.ui
        button = main.stage3_visualizer_button
        self.assertEqual(button.text(), "Stage-3 Visualizer")
        self.assertTrue(button.isEnabled())
        self.assertTrue(main.stats_panel.isAncestorOf(button))
        layout = main.stats_panel.layout()
        self.assertGreater(layout.indexOf(button), layout.indexOf(main.zini_explorer_button))
        self.assertIsNone(main._stage3_visualizer_launcher)
        self.assertEqual(main.tools_button.text(), "도구")
        self.assertEqual(main.tools_button.popupMode(), _MainToolButton.InstantPopup)
        self.assertIn(main.benchmark_statistics_action, main.tools_button.menu().actions())
        self.assertEqual(main.benchmark_statistics_action.text(), "벤치마크 통계")
        self.assertFalse(main.stats_panel.isAncestorOf(main.tools_button))
        self.assertNotIn("벤치마크 통계", [
            candidate.text() for candidate in main.stats_panel.findChildren(_MainPushButton)
        ])
        with _main_patch("benchmark_statistics_ui.BenchmarkStatisticsWindow") as factory:
            main.benchmark_statistics_action.trigger()
            main.benchmark_statistics_action.trigger()
            factory.assert_called_once_with(main)
            self.assertEqual(factory.return_value.show.call_count, 2)
            self.assertEqual(factory.return_value.raise_.call_count, 2)

    def test_main_construction_does_not_import_or_construct_launcher(self):
        real_import = _main_builtins.__import__

        def guard_import(name, *args, **kwargs):
            if name in ("stage3_visualizer_launcher", "stage3_execution_job"):
                raise AssertionError("Stage-3 must remain lazy during main construction")
            return real_import(name, *args, **kwargs)

        with _main_patch("builtins.__import__", side_effect=guard_import):
            other = _MainUI(_MainEngine(3, 3, 1))
            try:
                self.assertIsNone(other._stage3_visualizer_launcher)
            finally:
                other.close()
                other.deleteLater()

    def test_first_activation_constructs_once_then_shows_raises_and_activates(self):
        launcher_type = _main_launcher_module.Stage3VisualizerLauncherWindow
        with _main_patch.object(
            _main_launcher_module, "Stage3VisualizerLauncherWindow", wraps=launcher_type,
        ) as factory:
            launcher = self.open_launcher()
            self.assertIs(launcher.parent(), self.ui)
            self.assertTrue(launcher.isWindow())
            self.assertTrue(launcher.isVisible())
            with (
                _main_patch.object(launcher, "show") as show,
                _main_patch.object(launcher, "raise_") as raise_window,
                _main_patch.object(launcher, "activateWindow") as activate,
            ):
                self.ui.stage3_visualizer_button.click()
            factory.assert_called_once_with(self.ui)
            show.assert_called_once_with()
            raise_window.assert_called_once_with()
            activate.assert_called_once_with()
            self.assertIs(self.ui._stage3_visualizer_launcher, launcher)

    def test_launcher_close_clears_reference_reopen_ignores_old_closed_signal(self):
        old = self.open_launcher()
        self.assertTrue(old.close())
        self.assertIsNone(self.ui._stage3_visualizer_launcher)
        reopened = self.open_launcher()
        self.assertIsNot(reopened, old)
        # Deliver before deferred WA_DeleteOnClose deletion; sender must guard
        # against an old window clearing the newly retained launcher reference.
        old.closed.emit()
        self.assertIs(self.ui._stage3_visualizer_launcher, reopened)

    def test_main_close_shuts_down_active_stage3_and_preserves_auxiliary_cleanup(self):
        main = self.ui
        launcher = self.open_launcher()
        job = launcher.job
        launcher.run_button.click()
        self.assertEqual(job.state, "running")
        statistics = _MainMock()
        explorer = _MainMock()
        zini_process = _MainMock()
        zini_process.poll.return_value = None
        zini_process.wait.return_value = 0
        main._benchmark_statistics_window = statistics
        main._zini_explorer_window = explorer
        main._zini_process = zini_process
        main._zini_poll_timer.start()
        main._simple_auto_pending = True
        main._simple_auto_timer.start(60000)
        previous_zini_token = main._zini_job_token
        self.assertTrue(main.close())
        self.assertEqual(job.shutdown_calls, 1)
        self.assertEqual(job.shutdown_states, ["running"])
        self.assertEqual(job.state, "idle")
        self.assertIsNone(main._stage3_visualizer_launcher)
        statistics.close.assert_called_once_with()
        explorer.close.assert_called_once_with()
        zini_process.terminate.assert_called_once_with()
        zini_process.wait.assert_called_once()
        self.assertIsNone(main._zini_process)
        self.assertIsNone(main._zini_explorer_window)
        self.assertEqual(main._zini_job_token, previous_zini_token + 1)
        self.assertFalse(main._zini_poll_timer.isActive())
        self.assertFalse(main._simple_auto_timer.isActive())
        self.assertFalse(main._simple_auto_pending)

    def test_failed_stage3_shutdown_keeps_main_open_and_existing_cleanup_pending(self):
        main = self.ui
        launcher = self.open_launcher()
        job = launcher.job
        launcher.run_button.click()
        job.shutdown_error = RuntimeError("test child not yet reaped")
        statistics = _MainMock()
        main._benchmark_statistics_window = statistics
        event = _MainCloseEvent()
        with (
            _main_patch.object(main, "_invalidate_mouse_input") as invalidate,
            _main_patch.object(main, "_stop_simple_auto") as stop_auto,
            _main_patch.object(main, "_reset_zini_metric_job") as stop_zini,
        ):
            main.closeEvent(event)
            self.assertFalse(event.isAccepted())
            invalidate.assert_not_called()
            stop_auto.assert_not_called()
            stop_zini.assert_not_called()
        statistics.close.assert_not_called()
        self.assertIs(main._stage3_visualizer_launcher, launcher)
        self.assertEqual(job.shutdown_calls, 1)
        self.assertEqual(job.state, "running")
        job.shutdown_error = None
        self.assertTrue(main.close())
        self.assertEqual(job.shutdown_calls, 2)
        self.assertEqual(job.state, "idle")
        self.assertIsNone(main._stage3_visualizer_launcher)

    def snapshot_main(self):
        main = self.ui
        player = main._replay_player

        def state_of(instance):
            # Patched method guards are not engine/recorder state.
            return _main_deepcopy({key: value for key, value in instance.__dict__.items()
                                   if not callable(value)})

        return {
            "live_identity": id(main.engine),
            "live_state": state_of(main.engine),
            "replay": (main._replay_mode, id(player), id(main._replay_data),
                       id(main._replay_counter_timeline), main._replay_view_index,
                       player.current_index if player is not None else None),
            "replay_engine_identity": id(player.engine) if player is not None else None,
            "replay_engine_state": state_of(player.engine) if player is not None else None,
            "recorder_identity": id(main._replay_recorder),
            "recorder_state": state_of(main._replay_recorder),
            "analysis": (id(main._analysis_result), id(main._replay_analysis_result),
                         _main_deepcopy(main._analysis_observation), main._analysis_first_click,
                         main.analysis_status_label.text()),
            "board": {coord: (button.text(), button.analysis_overlay,
                              button.probability_text, button.toolTip())
                      for coord, button in main._buttons.items()},
            "counters": {name: item.text() for name, item in main._stat_value_items.items()},
            "settings": (main.difficulty_combo.currentText(), main.chord_combo.currentIndex(),
                         main.cell_size_spin.value(), main._chord_mode, main._cell_size,
                         main._normal_game_config, main.replay_playback_mode_combo.currentText(),
                         main.replay_index_interval_spin.value(), main.replay_time_speed_spin.value(),
                         main.analysis_checkbox.isChecked(), main.probability_checkbox.isChecked(),
                         main.reduction_checkbox.isChecked(), main.simple_auto_checkbox.isChecked(),
                         main.allow_guess_checkbox.isChecked()),
            "persisted_settings": {key: main._replay_settings.value(key)
                                   for key in main._replay_settings.allKeys()},
            "timers": (main._timer.isActive(), main._timer_running,
                       main._simple_auto_pending, main._simple_auto_timer.isActive(),
                       main._simple_auto_timer.interval(), main._replay_autoplay_timer.isActive(),
                       main._replay_time_anchor_wall, main._replay_time_anchor_replay,
                       main._replay_display_time_override),
            "zini": (main._zini_job_token, id(main._zini_process), id(main._zini_explorer_window),
                     main._zini_explorer.token, main._zini_explorer.state,
                     main._zini_explorer.current_index),
        }

    def set_analysis_fixture(self, replay=False):
        main = self.ui
        main._analysis_result = _MainAnalysis(None, None, "Retained analysis", {
            (2, 2): _MainOverlay(recommended=True),
        })
        main._analysis_observation = main._engine_for_current_mode().get_observation()
        main.analysis_status_label.setText("Retained analysis")
        if replay:
            main._replay_analysis_result = _MainReplayAnalysis(
                main._replay_player.current_index, main._analysis_result, None,
                _MainReplayComparison.NO_NEXT_ACTION, "Retained replay analysis",
            )
        main._render_live_analysis()

    def exercise_launcher_activity_without_main_changes(self):
        main = self.ui
        before = self.snapshot_main()
        execution = _main_execution_fixture()
        with _MainExitStack() as stack:
            engines = [self.engine]
            if main._replay_player is not None:
                engines.append(main._replay_player.engine)
            guards = []
            for engine in engines:
                for method in ("step", "reset", "configure", "reset_with_mines", "get_board_snapshot"):
                    guards.append(stack.enter_context(_main_patch.object(
                        engine, method, side_effect=AssertionError(f"Stage-3 called engine.{method}"),
                    )))
            for method in ("_enter_replay_mode", "_exit_replay_mode", "_record_replay_event"):
                guards.append(stack.enter_context(_main_patch.object(main, method)))
            guards.append(stack.enter_context(_main_patch.object(main._replay_recorder, "record_event")))
            if main._replay_player is not None:
                guards.append(stack.enter_context(_main_patch.object(main._replay_player, "go_to")))
            launcher = self.open_launcher()
            job = launcher.job
            launcher.game_index_edit.setText("17")
            launcher.run_button.click()
            self.assertEqual(job.started, [17])
            self.assertEqual(before, self.snapshot_main())
            job.finish_success(execution)
            viewer = launcher._visualizer_window
            self.assertIsNotNone(viewer)
            viewer.last_button.click()
            viewer.first_button.click()
            viewer.close()
            launcher.open_result_button.click()
            self.assertIsNotNone(launcher._visualizer_window)
            self.assertEqual(job.started, [17])
            self.assertEqual(before, self.snapshot_main())
            launcher.game_index_edit.setText("18")
            launcher.run_button.click()
            launcher.cancel_button.click()
            self.assertEqual(job.state, "cancelling")
            self.assertFalse(launcher.run_button.isEnabled())
            job.finish_cancel()
            self.assertIsNone(launcher._visualizer_window)
            self.assertIsNone(launcher._completed_execution)
            self.assertTrue(launcher.close())
            for guard in guards:
                guard.assert_not_called()
        self.assertEqual(before, self.snapshot_main())

    def test_launcher_run_result_navigation_cancel_preserve_live_game(self):
        self.engine.reset_with_mines(3, 3, 1, {(1, 1)})
        self.ui.on_left_click(0, 0)
        self.ui._stop_timer()
        self.ui.chord_combo.setCurrentIndex(1)
        self.ui.cell_size_spin.setValue(30)
        self.set_analysis_fixture()
        self.ui._simple_auto_pending = True
        self.ui._simple_auto_timer.start(60000)
        self.exercise_launcher_activity_without_main_changes()

    def test_launcher_run_result_navigation_cancel_preserve_active_replay(self):
        self.engine.reset_with_mines(3, 3, 1, {(1, 1)})
        self.ui.on_left_click(0, 0)
        data = _MainReplayData(_MainReplayBoard(3, 3, 1, {(1, 1)}), (
            _MainReplayEvent(1.0, 0, 0, "OPEN"),
            _MainReplayEvent(2.0, 1, 1, "FLAG"),
            _MainReplayEvent(3.0, 2, 0, "OPEN"),
        ))
        player = _MainReplayPlayer(data)
        player.go_to(1)
        self.ui._enter_replay_mode(player)
        self.set_analysis_fixture(replay=True)
        self.assertTrue(self.ui.stage3_visualizer_button.isEnabled())
        self.assertTrue(self.ui._replay_mode)
        self.exercise_launcher_activity_without_main_changes()


if __name__ == "__main__":
    unittest.main()
