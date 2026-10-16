"""Offscreen captured-source launcher ownership and terminal-race tests."""

from contextlib import ExitStack
from dataclasses import replace
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
    from PyQt5.QtWidgets import QApplication, QComboBox, QLabel, QLineEdit, QPushButton, QWidget
except ImportError:
    QApplication = None
else:
    import same_board_comparison_launcher as launcher
    from same_board_comparison_ui import SameBoardComparisonWindow

from core_engine import GameStatus
from same_board_playback import ComparisonRun
from same_board_runner import SameBoardExecution, run_same_board_comparison
from tests.test_same_board_runner import human_context


if QApplication is not None:
    class FakeSameBoardExecutionJob(QObject):
        succeeded = pyqtSignal(object, object)
        failed = pyqtSignal(object, str)
        cancelled = pyqtSignal(object)

        def __init__(self, parent=None):
            super().__init__(parent)
            self.state = "idle"
            self.started = []
            self.next_token = 1
            self.start_error = None
            self.start_hook = None
            self.cancel_calls = 0
            self.cancel_hook = None
            self.shutdown_calls = 0
            self.shutdown_error = None
            self.shutdown_hook = None

        def start(self, context):
            if self.start_error is not None:
                raise self.start_error
            if self.state != "idle":
                raise RuntimeError("job is busy")
            if self.start_hook is not None:
                self.start_hook()
            token = self.next_token
            self.next_token += 1
            self.started.append((token, context))
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


    class FakeResultWindow(QWidget):
        closed = pyqtSignal()

        def __init__(self, execution, parent=None):
            super().__init__(parent, Qt.Window)
            self.setAttribute(Qt.WA_DeleteOnClose)
            self.execution = execution
            self.refuse_close = False
            self.close_hook = None
            self._closed = False

        def closeEvent(self, event):
            if self.close_hook is not None:
                self.close_hook()
            if self.refuse_close:
                event.ignore()
                return
            super().closeEvent(event)
            if event.isAccepted() and not self._closed:
                self._closed = True
                self.closed.emit()


@unittest.skipIf(QApplication is None, "PyQt5 unavailable")
class SameBoardComparisonLauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        # Real execution evidence is prepared before any UI is constructed.
        cls.win = run_same_board_comparison(human_context(with_trace=True))
        cls.loss = run_same_board_comparison(human_context(mined_origin=True, with_trace=True))

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.job_factory = self.stack.enter_context(patch.object(
            launcher, "SameBoardExecutionJob", wraps=FakeSameBoardExecutionJob,
        ))
        self.viewer_factory = self.stack.enter_context(patch.object(
            launcher, "SameBoardComparisonWindow", wraps=FakeResultWindow,
        ))
        for producer in (
            "same_board_runner.run_same_board_comparison",
            "same_board_runner.compose_same_board_execution",
            "simple_runner.run_simple", "stage3_runner.run_stage3",
            "stage3_planner.plan_position", "benchmark_board.generate_board",
            "benchmark_modeled_time.authenticate_model_c",
            "benchmark_modeled_time.evaluate_ordered_actions", "subprocess.Popen",
        ):
            self.stack.enter_context(patch(producer, side_effect=AssertionError(producer)))
        self.windows = []
        self.window = self.make_window(self.win)
        self.job = self.window.job
        self.addCleanup(self.close_windows)

    def make_window(self, execution):
        window = launcher.SameBoardComparisonLauncherWindow(
            execution.context, source_description="currently loaded Replay",
        )
        self.windows.append(window)
        return window

    def close_windows(self):
        for window in self.windows:
            if window.job is not None:
                window.job.shutdown_error = None
                window.job.shutdown_hook = None
            viewer = window._result_window
            if isinstance(viewer, FakeResultWindow):
                viewer.refuse_close = False
                viewer.close_hook = None
            window.close()
        self.app.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()

    def start_request(self, window=None):
        window = window or self.window
        window.run_button.click()
        return window._active_token

    def complete_request(self, window=None, execution=None):
        window = window or self.window
        self.start_request(window)
        window.job.finish_success(execution or self.win)
        return window._result_window

    def assert_idle_controls(self):
        self.assertIsNone(self.window._active_token)
        self.assertTrue(self.window.run_button.isEnabled())
        self.assertFalse(self.window.cancel_button.isEnabled())

    def assert_disabled_controls(self):
        for button in (self.window.run_button, self.window.cancel_button,
                       self.window.open_result_button):
            self.assertFalse(button.isEnabled())

    def test_construction_retains_context_owns_one_job_and_no_source_selector(self):
        window = self.window
        self.assertEqual(window.windowType(), Qt.Window)
        self.assertTrue(window.testAttribute(Qt.WA_DeleteOnClose))
        self.assertIs(window.context, self.win.context)
        self.assertIs(window.context.human_replay.mouse_trace, self.win.context.human_replay.mouse_trace)
        self.job_factory.assert_called_once_with(window)
        self.assertIs(self.job.parent(), window)
        self.assertEqual(window.findChildren(QComboBox), [])
        self.assertEqual(window.findChildren(QLineEdit), [])
        self.assertEqual([button.text() for button in window.findChildren(QPushButton)],
                         ["Run", "Cancel", "Open Result"])
        self.assertIn("Ready", window.status_label.text())
        self.assert_idle_controls()
        self.assertFalse(window.open_result_button.isEnabled())
        self.assertEqual(self.job.started, [])
        self.viewer_factory.assert_not_called()

    def test_captured_facts_and_provenance_are_plain_and_factual(self):
        labels = " ".join(label.text() for label in self.window.findChildren(QLabel))
        self.assertIn("currently loaded Replay", labels)
        self.assertIn("4", labels)
        self.assertIn("WON", labels)
        self.assertIn(str(len(self.win.context.human_replay.events)), labels)
        self.assertIn(self.win.context.layout.board_fingerprint, labels)
        self.assertIn("full-game Human recording", labels)
        self.assertIn("do not prove exclusively Human historical input", labels)
        self.assertIn("Auto input may be present", labels)
        self.assertEqual(self.window.status_label.textFormat(), Qt.PlainText)

    def test_run_uses_exact_context_retains_token_and_blocks_duplicate_start(self):
        token = self.start_request()
        self.assertEqual(self.job.started, [(token, self.win.context)])
        self.assertIs(self.job.started[0][1], self.window.context)
        self.assertIs(type(token), int)
        self.assertIn("Running", self.window.status_label.text())
        self.assertFalse(self.window.run_button.isEnabled())
        self.assertTrue(self.window.cancel_button.isEnabled())
        self.assertFalse(self.window.open_result_button.isEnabled())
        self.window._run()
        self.assertEqual(len(self.job.started), 1)
        self.assertEqual(self.job.shutdown_calls, 0)

    def test_arbitrary_size_transport_token_is_retained_without_conversion(self):
        self.job.next_token = 2 ** 140 + 13
        token = self.start_request()
        self.assertEqual(token, 2 ** 140 + 13)
        self.job.finish_success(self.win)
        self.assertIs(self.window._completed_execution, self.win)

    def test_success_retains_exact_result_and_opens_one_parented_viewer(self):
        viewer = self.complete_request()
        self.assertIs(self.window._completed_execution, self.win)
        self.assertIs(viewer.execution, self.win)
        self.assertIs(viewer.parent(), self.window)
        self.assertTrue(viewer.isVisible())
        self.viewer_factory.assert_called_once_with(self.win, self.window)
        self.assert_idle_controls()
        self.assertTrue(self.window.open_result_button.isEnabled())
        self.assertIn("Completed", self.window.status_label.text())
        self.assertEqual(self.job.shutdown_calls, 0)

    def test_legitimate_mined_origin_losses_are_completed_success_without_retry(self):
        window = self.make_window(self.loss)
        viewer = self.complete_request(window, self.loss)
        self.assertIs(viewer.execution, self.loss)
        self.assertIs(window._completed_execution.context, self.loss.context)
        self.assertIs(self.loss.stage2_metrics.outcome, GameStatus.LOST)
        self.assertIs(self.loss.stage3_metrics.outcome, GameStatus.LOST)
        self.assertIn("Completed", window.status_label.text())
        self.assertEqual(len(window.job.started), 1)
        self.assertTrue(window.open_result_button.isEnabled())

    def test_success_requires_original_context_identity_even_if_equal(self):
        self.start_request()
        other_context = human_context(with_trace=True)
        self.assertEqual(other_context, self.win.context)
        self.assertIsNot(other_context, self.win.context)
        self.job.finish_success(replace(self.win, context=other_context))
        self.assertIsNone(self.window._completed_execution)
        self.assertIsNone(self.window._result_window)
        self.assertIn("Failed", self.window.status_label.text())
        self.assertIn("context", self.window.status_label.text().lower())
        self.viewer_factory.assert_not_called()
        self.assert_idle_controls()

    def test_success_requires_exact_native_execution_type(self):
        class DerivedExecution(SameBoardExecution):
            pass

        for unexpected in (object(), DerivedExecution(**vars(self.win))):
            with self.subTest(result_type=type(unexpected).__name__):
                self.start_request()
                self.job.finish_success(unexpected)
                self.assertIsNone(self.window._completed_execution)
                self.assertIn("Failed", self.window.status_label.text())
                self.assert_idle_controls()
        self.viewer_factory.assert_not_called()

    def test_failure_is_plain_diagnostic_without_fabricated_result(self):
        self.start_request()
        self.job.finish_failure("<worker failed>")
        self.assertIn("Failed", self.window.status_label.text())
        self.assertIn("<worker failed>", self.window.status_label.text())
        self.assertIsNone(self.window._completed_execution)
        self.assertIsNone(self.window._result_window)
        self.assert_idle_controls()
        self.assertFalse(self.window.open_result_button.isEnabled())

    def test_start_exception_is_caught_and_idle_controls_recover(self):
        self.job.start_error = RuntimeError("cannot start")
        self.start_request()
        self.assertIn("cannot start", self.window.status_label.text())
        self.assert_idle_controls()
        self.assertEqual(self.job.started, [])
        self.viewer_factory.assert_not_called()

    def test_cancel_records_intent_before_job_call_and_never_waits(self):
        token = self.start_request()

        def inspect_cancel():
            self.assertTrue(self.window._cancel_requested)
            self.assertIn("Cancelling", self.window.status_label.text())
            self.assertFalse(self.window.cancel_button.isEnabled())
            self.job.succeeded.emit(token, self.win)

        self.job.cancel_hook = inspect_cancel
        self.window.cancel_button.click()
        self.window._cancel()
        self.window._run()
        self.assertEqual(self.job.cancel_calls, 1)
        self.assertEqual(self.job.shutdown_calls, 0)
        self.assertEqual(self.window._active_token, token)
        self.assertIsNone(self.window._completed_execution)
        self.assert_disabled_controls()
        self.viewer_factory.assert_not_called()
        self.job.finish_cancel()
        self.assertIn("Cancelled", self.window.status_label.text())
        self.assertFalse(self.window._cancel_requested)
        self.assert_idle_controls()

    def test_cancel_exception_preserves_intent_and_blocks_result_until_terminal(self):
        token = self.start_request()
        with patch.object(self.job, "cancel", side_effect=RuntimeError("cancel refused")):
            self.window._cancel()
        self.assertTrue(self.window._cancel_requested)
        self.assertIn("cancel refused", self.window.status_label.text())
        self.job.succeeded.emit(token, self.win)
        self.assertIsNone(self.window._completed_execution)
        self.assert_disabled_controls()
        self.job.finish_failure("cleanup needed")
        self.assertFalse(self.window._cancel_requested)
        self.assert_idle_controls()

    def test_cleanup_failure_clears_token_but_keeps_run_and_open_blocked(self):
        token = self.start_request()
        self.job.state = "cancelling"
        self.job.failed.emit(token, "cleanup failed")
        self.assertIsNone(self.window._active_token)
        self.assert_disabled_controls()
        self.window._run()
        self.window._open_result()
        self.assertEqual(len(self.job.started), 1)
        self.assertIs(self.window.job, self.job)
        self.assertTrue(self.window.close())
        self.assertEqual(self.job.shutdown_calls, 1)

    def test_nonidle_job_also_blocks_retained_result_open(self):
        viewer = self.complete_request()
        viewer.close()
        self.job.state = "cancelling"
        self.window._update_controls()
        self.assert_disabled_controls()
        self.window._open_result()
        self.window._run()
        self.assertEqual(self.viewer_factory.call_count, 1)
        self.assertEqual(len(self.job.started), 1)
        self.assertIs(self.window._completed_execution, self.win)

    def test_stale_bool_float_and_unrelated_tokens_are_inert(self):
        old_token = self.start_request()
        self.job.finish_cancel()
        current = self.start_request()
        before = self.window.status_label.text()
        for token in (old_token, current + 1, True, False, float(current), None, str(current)):
            with self.subTest(token=token):
                self.job.succeeded.emit(token, self.win)
                self.job.failed.emit(token, "stale error")
                self.job.cancelled.emit(token)
                self.assertEqual(self.window._active_token, current)
                self.assertEqual(self.window.status_label.text(), before)
                self.assertIsNone(self.window._completed_execution)
        self.viewer_factory.assert_not_called()

    def test_bool_and_float_equal_to_first_token_cannot_complete_it(self):
        self.assertEqual(self.start_request(), 1)
        for token in (True, 1.0):
            self.job.succeeded.emit(token, self.win)
            self.job.failed.emit(token, "wrong type")
            self.job.cancelled.emit(token)
            self.assertEqual(self.window._active_token, 1)
            self.assertIsNone(self.window._completed_execution)
        self.viewer_factory.assert_not_called()

    def test_duplicate_terminal_callbacks_preserve_completed_result(self):
        viewer = self.complete_request()
        token = self.job.started[-1][0]
        before = self.window.status_label.text()
        self.job.succeeded.emit(token, self.loss)
        self.job.failed.emit(token, "late failure")
        self.job.cancelled.emit(token)
        self.assertIs(self.window._completed_execution, self.win)
        self.assertIs(self.window._result_window, viewer)
        self.assertEqual(self.window.status_label.text(), before)
        self.assertEqual(self.viewer_factory.call_count, 1)

    def test_close_viewer_retains_result_and_reopens_without_new_job(self):
        viewer = self.complete_request()
        self.assertTrue(viewer.close())
        self.assertIsNone(self.window._result_window)
        self.assertIs(self.window._completed_execution, self.win)
        self.window.open_result_button.click()
        reopened = self.window._result_window
        self.assertIsNot(reopened, viewer)
        self.assertIs(reopened.execution, self.win)
        self.assertEqual(len(self.job.started), 1)
        self.assertEqual(self.viewer_factory.call_count, 2)

    def test_real_viewer_recreation_has_accepted_fresh_playback_defaults(self):
        with patch.object(launcher, "SameBoardComparisonWindow", wraps=SameBoardComparisonWindow):
            viewer = self.complete_request()
            viewer.last_button.click()
            viewer.mouse_trace_checkbox.setChecked(True)
            viewer.run_selector.setCurrentIndex(1)
            self.assertTrue(viewer.close())
            self.window._open_result()
            reopened = self.window._result_window
            self.assertIs(reopened.execution, self.win)
            self.assertIs(reopened.playback.selected_run, ComparisonRun.HUMAN)
            for run in ComparisonRun:
                self.assertEqual(reopened.playback.index_for(run), 0)
            self.assertFalse(reopened.mouse_trace_checkbox.isChecked())
            self.assertEqual(len(self.job.started), 1)

    def test_existing_viewer_is_shown_raised_and_activated_without_recreation(self):
        viewer = self.complete_request()
        with patch.object(viewer, "show") as show, patch.object(viewer, "raise_") as raise_, \
                patch.object(viewer, "activateWindow") as activate:
            self.window.open_result_button.click()
            show.assert_called_once_with()
            raise_.assert_called_once_with()
            activate.assert_called_once_with()
        self.assertEqual(self.viewer_factory.call_count, 1)
        self.assertEqual(len(self.job.started), 1)

    def test_viewer_construction_failure_retains_result_and_can_retry(self):
        self.start_request()
        self.viewer_factory.side_effect = RuntimeError("viewer unavailable")
        self.job.finish_success(self.win)
        self.assertIs(self.window._completed_execution, self.win)
        self.assertIsNone(self.window._result_window)
        self.assertIn("Result window open failed", self.window.status_label.text())
        self.assertIn("viewer unavailable", self.window.status_label.text())
        self.assertTrue(self.window.open_result_button.isEnabled())
        self.viewer_factory.side_effect = None
        self.window.open_result_button.click()
        self.assertIs(self.window._result_window.execution, self.win)
        self.assertEqual(len(self.job.started), 1)

    def test_new_run_closes_viewer_then_clears_result_before_start(self):
        viewer = self.complete_request()
        order = []

        def viewer_closing():
            self.assertIs(self.window._completed_execution, self.win)
            order.append("viewer close")

        def job_starting():
            self.assertIsNone(self.window._result_window)
            self.assertIsNone(self.window._completed_execution)
            order.append("job start")

        viewer.close_hook = viewer_closing
        self.job.start_hook = job_starting
        self.start_request()
        self.assertEqual(order, ["viewer close", "job start"])
        self.assertTrue(viewer._closed)
        self.assertIs(self.job.started[-1][1], self.win.context)
        self.assertIsNone(self.window._completed_execution)

    def test_refused_viewer_close_preserves_old_result_and_prevents_run(self):
        viewer = self.complete_request()
        viewer.refuse_close = True
        self.window._run()
        self.assertIs(self.window._completed_execution, self.win)
        self.assertIs(self.window._result_window, viewer)
        self.assertEqual(len(self.job.started), 1)
        self.assertTrue(self.window.open_result_button.isEnabled())

    def test_old_viewer_closed_signal_cannot_clear_replacement(self):
        old = self.complete_request()
        self.start_request()
        self.job.finish_success(self.win)
        new = self.window._result_window
        old.closed.emit()
        self.assertIs(self.window._result_window, new)

    def test_close_shutdown_precedes_viewer_close_and_emits_once(self):
        viewer = self.complete_request()
        order = []
        self.job.shutdown_hook = lambda: order.append("shutdown")
        viewer.close_hook = lambda: order.append("viewer close")
        signal = QSignalSpy(self.window.closed)
        self.assertTrue(self.window.close())
        self.assertEqual(order, ["shutdown", "viewer close"])
        self.assertTrue(self.window._shutdown_started)
        self.assertTrue(self.window._closed)
        self.assertIsNone(self.window.job)
        self.assertIsNone(self.window._result_window)
        self.assertIsNone(self.window._completed_execution)
        self.assertIsNone(self.window._active_token)
        self.assertEqual(len(signal), 1)
        event = QCloseEvent()
        self.window.closeEvent(event)
        self.assertTrue(event.isAccepted())
        self.assertEqual(self.job.shutdown_calls, 1)
        self.assertEqual(len(signal), 1)

    def test_active_close_marks_intent_before_shutdown_and_ignores_callbacks(self):
        token = self.start_request()

        def during_shutdown():
            self.assertTrue(self.window._shutdown_started)
            self.assertTrue(self.window._cancel_requested)
            self.assert_disabled_controls()
            self.job.succeeded.emit(token, self.win)
            self.job.failed.emit(token, "during shutdown")
            self.job.cancelled.emit(token)

        self.job.shutdown_hook = during_shutdown
        self.assertTrue(self.window.close())
        self.assertEqual(self.job.shutdown_calls, 1)
        self.assertEqual(self.job.cancel_calls, 0)
        self.viewer_factory.assert_not_called()
        self.assertIsNone(self.window._completed_execution)

    def test_shutdown_failure_retains_ownership_and_permanently_disables_execution(self):
        token = self.start_request()
        self.job.shutdown_error = RuntimeError("child not reaped")
        signal = QSignalSpy(self.window.closed)
        self.assertFalse(self.window.close())
        self.assertIs(self.window.job, self.job)
        self.assertIs(self.window.context, self.win.context)
        self.assertEqual(self.window._active_token, token)
        self.assertFalse(self.window._closed)
        self.assertTrue(self.window._shutdown_started)
        self.assertIn("child not reaped", self.window.status_label.text())
        self.assert_disabled_controls()
        self.job.state = "idle"  # Even becoming idle cannot resurrect execution.
        self.job.succeeded.emit(token, self.win)
        self.job.failed.emit(token, "late failure")
        self.job.cancelled.emit(token)
        self.window._update_controls()
        self.window._run()
        self.window._cancel()
        self.window._open_result()
        self.assert_disabled_controls()
        self.assertEqual(len(self.job.started), 1)
        self.assertEqual(self.job.cancel_calls, 0)
        self.viewer_factory.assert_not_called()
        self.assertEqual(len(signal), 0)
        self.job.shutdown_error = None
        self.assertTrue(self.window.close())
        self.assertEqual(self.job.shutdown_calls, 2)
        self.assertEqual(len(signal), 1)

    def test_shutdown_failure_keeps_completed_result_and_viewer_for_close_retry(self):
        viewer = self.complete_request()
        self.job.shutdown_error = RuntimeError("directory cleanup failed")
        with patch.object(viewer, "close", wraps=viewer.close) as close:
            self.assertFalse(self.window.close())
            close.assert_not_called()
        self.assertIs(self.window._result_window, viewer)
        self.assertIs(self.window._completed_execution, self.win)
        self.assert_disabled_controls()
        self.job.shutdown_error = None
        self.assertTrue(self.window.close())
        self.assertTrue(viewer._closed)

    def test_viewer_refuses_close_after_shutdown_without_resurrecting_run(self):
        viewer = self.complete_request()
        viewer.refuse_close = True
        signal = QSignalSpy(self.window.closed)
        self.assertFalse(self.window.close())
        self.assertEqual(self.job.shutdown_calls, 1)
        self.assertEqual(self.job.state, "idle")
        self.assertIs(self.window.job, self.job)
        self.assertIs(self.window._completed_execution, self.win)
        self.assertIs(self.window._result_window, viewer)
        self.assertTrue(self.window._shutdown_started)
        self.assert_disabled_controls()
        self.window._run()
        self.window._open_result()
        self.assertEqual(len(self.job.started), 1)
        self.assertEqual(self.viewer_factory.call_count, 1)
        self.assertEqual(len(signal), 0)
        viewer.refuse_close = False
        self.assertTrue(self.window.close())
        self.assertEqual(self.job.shutdown_calls, 2)
        self.assertEqual(len(signal), 1)

    def test_ignored_base_close_does_not_begin_shutdown(self):
        self.start_request()
        signal = QSignalSpy(self.window.closed)
        event = QCloseEvent()
        with patch.object(QWidget, "closeEvent", side_effect=lambda event: event.ignore()):
            self.window.closeEvent(event)
        self.assertFalse(event.isAccepted())
        self.assertFalse(self.window._shutdown_started)
        self.assertFalse(self.window._closed)
        self.assertEqual(self.job.shutdown_calls, 0)
        self.assertEqual(len(signal), 0)
        self.assertTrue(self.window.cancel_button.isEnabled())

    def test_callbacks_and_operations_after_close_are_inert(self):
        token = self.start_request()
        self.assertTrue(self.window.close())
        self.job.succeeded.emit(token, self.win)
        self.job.failed.emit(token, "late failure")
        self.job.cancelled.emit(token)
        self.window._run()
        self.window._cancel()
        self.window._open_result()
        self.assertEqual(len(self.job.started), 1)
        self.assertEqual(self.job.shutdown_calls, 1)
        self.assertEqual(self.job.cancel_calls, 0)
        self.viewer_factory.assert_not_called()
        self.assertIsNone(self.window._completed_execution)


if __name__ == "__main__":
    unittest.main()
