"""Own one captured Human context, its comparison job and completed result viewer."""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from same_board_comparison import HumanComparisonContext
from same_board_comparison_ui import SameBoardComparisonWindow
from same_board_execution_job import SameBoardExecutionJob
from same_board_runner import SameBoardExecution


class SameBoardComparisonLauncherWindow(QWidget):
    """One immutable source per window; only this owner controls the worker.

    Closing the result viewer retains the completed execution for reopening.
    Once shutdown begins this launcher can only retry close, never run again.
    """

    closed = pyqtSignal()

    def __init__(self, context, parent=None, *, source_description=None):
        if type(context) is not HumanComparisonContext:
            raise TypeError("An admitted HumanComparisonContext is required.")
        super().__init__(parent, Qt.Window)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle("Same-board Comparison")
        self.context = context
        self._active_token = None
        self._cancel_requested = False
        self._completed_execution = None
        self._result_window = None
        self._shutdown_started = False
        self._closed = False
        self.job = SameBoardExecutionJob(self)
        self.job.succeeded.connect(self._on_succeeded)
        self.job.failed.connect(self._on_failed)
        self.job.cancelled.connect(self._on_cancelled)

        layout = QVBoxLayout(self)
        board = context.layout.board
        source = "One captured full-game Human recording"
        if source_description:
            source += f"\nCaptured source: {source_description}"
        self.source_label = QLabel(source)
        self.facts_label = QLabel(
            f"Board: {board.width} × {board.height} · Mines: {board.num_mines}\n"
            f"Human final outcome: {context.terminal_status.name} · "
            f"Human events: {len(context.human_replay.events)}"
        )
        self.fingerprint_label = QLabel(f"Layout fingerprint: {context.layout.board_fingerprint}")
        self.provenance_label = QLabel(
            "Submitted as a full-game Human recording. Human metadata, declaration "
            "and successful reconstruction do not prove exclusively Human historical "
            "input; recorded Auto input may be present."
        )
        for label in (self.source_label, self.facts_label, self.fingerprint_label,
                      self.provenance_label):
            label.setTextFormat(Qt.PlainText)
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            layout.addWidget(label)
        controls = QHBoxLayout()
        self.run_button = QPushButton("Run")
        self.cancel_button = QPushButton("Cancel")
        self.open_result_button = QPushButton("Open Result")
        self.run_button.clicked.connect(self._run)
        self.cancel_button.clicked.connect(self._cancel)
        self.open_result_button.clicked.connect(self._open_result)
        for button in (self.run_button, self.cancel_button, self.open_result_button):
            controls.addWidget(button)
        layout.addLayout(controls)
        self.status_label = QLabel("Ready")
        self.status_label.setTextFormat(Qt.PlainText)
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.status_label)
        self._update_controls()
        self.resize(520, self.sizeHint().height())

    def _update_controls(self):
        available = not self._shutdown_started and not self._closed
        idle = self.job is not None and self.job.state == "idle"
        can_run = available and self._active_token is None and idle
        self.run_button.setEnabled(can_run)
        self.cancel_button.setEnabled(
            available and self._active_token is not None and not self._cancel_requested,
        )
        self.open_result_button.setEnabled(can_run and self._completed_execution is not None)

    def _run(self):
        if (self._shutdown_started or self._closed or self._active_token is not None
                or self.job.state != "idle"):
            return
        if not self._close_result():
            return
        self._completed_execution = None
        self._cancel_requested = False
        try:
            # The accepted job reports even startup failures after returning a token.
            self._active_token = self.job.start(self.context)
        except Exception as exc:
            self.status_label.setText(f"Failed to start: {exc}")
        else:
            self.status_label.setText("Running")
        self._update_controls()

    def _cancel(self):
        if (self._shutdown_started or self._closed or self._active_token is None
                or self._cancel_requested):
            return
        # Set intent first: coincident success must not attach a result.
        self._cancel_requested = True
        self.status_label.setText("Cancelling")
        self._update_controls()
        try:
            self.job.cancel()
        except Exception as exc:
            self.status_label.setText(f"Cancellation request failed: {exc}")

    def _matches_active_token(self, token):
        return (
            not self._shutdown_started and not self._closed
            and type(token) is int and token == self._active_token
        )

    def _on_succeeded(self, token, execution):
        if not self._matches_active_token(token) or self._cancel_requested:
            return
        # The job owns transport validation. Here only bind its result to this owner.
        if type(execution) is not SameBoardExecution or execution.context is not self.context:
            self._on_failed(token, "Comparison result type or captured context identity mismatch.")
            return
        self._active_token = None
        self._cancel_requested = False
        self._completed_execution = execution
        self.status_label.setText(
            f"Completed — Stage 2: {execution.stage2_metrics.outcome.name}; "
            f"Stage 3: {execution.stage3_metrics.outcome.name}"
        )
        self._update_controls()
        self._open_result()

    def _on_failed(self, token, diagnostic):
        if not self._matches_active_token(token):
            return
        self._active_token = None
        self._cancel_requested = False
        self._completed_execution = None
        self.status_label.setText(f"Failed: {diagnostic}")
        self._update_controls()

    def _on_cancelled(self, token):
        if not self._matches_active_token(token):
            return
        self._active_token = None
        self._cancel_requested = False
        self._completed_execution = None
        self.status_label.setText("Cancelled")
        self._update_controls()

    def _open_result(self):
        if (self._shutdown_started or self._closed or self._active_token is not None
                or self.job.state != "idle" or self._completed_execution is None):
            return
        if self._result_window is None:
            try:
                viewer = SameBoardComparisonWindow(self._completed_execution, self)
            except Exception as exc:
                self.status_label.setText(f"Result window open failed: {exc}")
                return
            self._result_window = viewer
            viewer.closed.connect(self._on_result_closed)
        self._result_window.show()
        self._result_window.raise_()
        self._result_window.activateWindow()

    def _on_result_closed(self):
        if self.sender() is self._result_window:
            self._result_window = None

    def _close_result(self):
        viewer = self._result_window
        if viewer is not None:
            if not viewer.close():
                self.status_label.setText("Result window close failed; retry close.")
                return False
            self._result_window = None
        return True

    def closeEvent(self, event):
        super().closeEvent(event)
        if not event.isAccepted() or self._closed:
            return
        # shutdown() is irreversible even when reaping/cleanup fails. Preserve
        # ownership for a close retry without ever re-enabling execution.
        self._shutdown_started = True
        if self._active_token is not None:
            self._cancel_requested = True
        self._update_controls()
        try:
            # Bounded waits belong only to final shutdown, never Run/Cancel.
            self.job.shutdown()
        except Exception as exc:
            self.status_label.setText(f"Close/shutdown failed: {exc}; retry close.")
            event.ignore()
            return
        if not self._close_result():
            event.ignore()
            return
        self.job = None
        self._active_token = None
        self._completed_execution = None
        self._closed = True
        self._update_controls()
        self.closed.emit()
