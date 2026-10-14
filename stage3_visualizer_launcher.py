"""Own one Stage-3 job and the viewer for its most recent completed execution."""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from stage3_execution_job import Stage3ExecutionJob
from stage3_visualizer_ui import Stage3VisualizerWindow


class Stage3VisualizerLauncherWindow(QWidget):
    """Independent benchmark controls; no live-game or replay state is needed."""

    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle("Stage-3 Visualizer 실행")
        self._active_token = None
        self._completed_execution = None
        self._visualizer_window = None
        self._cancel_requested = False
        self._closing = False
        self._closed = False
        self.job = Stage3ExecutionJob(self)
        self.job.succeeded.connect(self._on_succeeded)
        self.job.failed.connect(self._on_failed)
        self.job.cancelled.connect(self._on_cancelled)

        layout = QVBoxLayout(self)
        self.benchmark_label = QLabel("Benchmark: EXPERT_GENERAL_V1")
        self.algorithm_label = QLabel("Algorithm: Stage-3 V1 / Model C")
        layout.addWidget(self.benchmark_label)
        layout.addWidget(self.algorithm_label)
        index_row = QHBoxLayout()
        index_label = QLabel("Game Index:")
        self.game_index_edit = QLineEdit("0")
        self.game_index_edit.setAccessibleName("Stage-3 game index")
        self.game_index_edit.setToolTip("0 이상의 정수 (십진수)")
        index_label.setBuddy(self.game_index_edit)
        index_row.addWidget(index_label)
        index_row.addWidget(self.game_index_edit)
        layout.addLayout(index_row)
        controls = QHBoxLayout()
        self.run_button = QPushButton("Run")
        self.cancel_button = QPushButton("Cancel")
        self.open_result_button = QPushButton("결과 열기")
        self.run_button.clicked.connect(self.on_run)
        self.cancel_button.clicked.connect(self.on_cancel)
        self.open_result_button.clicked.connect(self.on_open_result)
        self.game_index_edit.returnPressed.connect(self.on_run)
        for button in (self.run_button, self.cancel_button, self.open_result_button):
            controls.addWidget(button)
        layout.addLayout(controls)
        self.status_label = QLabel("대기 중")
        self.status_label.setTextFormat(Qt.PlainText)
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.status_label)
        self._update_controls()
        self.resize(420, self.sizeHint().height())

    def _update_controls(self):
        available = not self._closing and not self._closed
        busy = self._active_token is not None or (self.job is not None and self.job.state != "idle")
        self.game_index_edit.setEnabled(available and not busy)
        self.run_button.setEnabled(available and not busy)
        self.cancel_button.setEnabled(
            available and self._active_token is not None and not self._cancel_requested,
        )
        self.open_result_button.setEnabled(
            available and not busy and self._completed_execution is not None,
        )

    def on_run(self):
        if self._closing or self._closed or self._active_token is not None or self.job.state != "idle":
            return
        text = self.game_index_edit.text().strip()
        try:
            if not text or not text.isascii() or not text.isdecimal():
                raise ValueError("not a nonnegative decimal integer")
            game_index = int(text)
        except ValueError:
            self.status_label.setText("Game Index에 0 이상의 정수를 입력하세요.")
            return
        if not self._close_visualizer():
            return
        self._completed_execution = None
        self._cancel_requested = False
        try:
            # The job delivers even startup failures after start returns its token.
            self._active_token = self.job.start(game_index)
        except Exception as exc:
            self.status_label.setText(f"실행 시작 실패: {exc}")
        else:
            self.status_label.setText(f"실행 중 — Game Index {game_index}")
        self._update_controls()

    def on_cancel(self):
        if self._closing or self._closed or self._active_token is None or self._cancel_requested:
            return
        # Record intent before calling the job so a coincident success is inert.
        self._cancel_requested = True
        self.status_label.setText("취소 중…")
        self._update_controls()
        try:
            self.job.cancel()
        except Exception as exc:
            self.status_label.setText(f"취소 요청 실패: {exc}")

    def _matches_active_token(self, token):
        return (
            not self._closing and not self._closed
            and type(token) is int and token == self._active_token
        )

    def _on_succeeded(self, token, execution):
        if not self._matches_active_token(token) or self._cancel_requested:
            return
        self._active_token = None
        self._completed_execution = execution
        self.status_label.setText(
            f"완료 — Game Index {execution.board.game_index}: {execution.result.status.name}"
        )
        self._update_controls()
        self.on_open_result()

    def _on_failed(self, token, diagnostic):
        if not self._matches_active_token(token):
            return
        self._active_token = None
        self._cancel_requested = False
        self._completed_execution = None
        self.status_label.setText(f"실행 실패: {diagnostic}")
        self._update_controls()

    def _on_cancelled(self, token):
        if not self._matches_active_token(token):
            return
        self._active_token = None
        self._cancel_requested = False
        self._completed_execution = None
        self.status_label.setText("취소됨")
        self._update_controls()

    def on_open_result(self):
        if (
            self._closing or self._closed or self._active_token is not None
            or self.job.state != "idle" or self._completed_execution is None
        ):
            return
        if self._visualizer_window is None:
            try:
                viewer = Stage3VisualizerWindow(self._completed_execution, self)
            except Exception as exc:
                self.status_label.setText(f"결과 창 열기 실패: {exc}")
                return
            self._visualizer_window = viewer
            viewer.closed.connect(self._on_visualizer_closed)
        self._visualizer_window.show()
        self._visualizer_window.raise_()
        self._visualizer_window.activateWindow()

    def _on_visualizer_closed(self):
        if self.sender() is self._visualizer_window:
            self._visualizer_window = None

    def _close_visualizer(self):
        viewer = self._visualizer_window
        if viewer is not None:
            if not viewer.close():
                self.status_label.setText("결과 창을 닫지 못했습니다.")
                return False
            self._visualizer_window = None
        return True

    def closeEvent(self, event):
        super().closeEvent(event)
        if not event.isAccepted() or self._closed:
            return
        self._closing = True
        self._cancel_requested = self._active_token is not None
        self._update_controls()
        try:
            # Only final shutdown can wait; keep ownership if reaping fails.
            self.job.shutdown()
        except Exception as exc:
            self._closing = False
            self.status_label.setText(f"종료 실패: {exc}")
            self._update_controls()
            event.ignore()
            return
        if not self._close_visualizer():
            self._closing = False
            self._update_controls()
            event.ignore()
            return
        self.job = None
        self._active_token = None
        self._completed_execution = None
        self._closed = True
        self._update_controls()
        self.closed.emit()
