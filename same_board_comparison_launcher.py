"""Own one captured Human context, its comparison job and completed result viewer.

Before a run the user selects the algorithms to execute (default: Stage 2
Simple and Stage 3 V1). Selecting both of those uses the unchanged existing job
and result window; every other selected algorithm runs afterwards, one child
at a time, in ``SameBoardAlgorithmQueue``. When any such algorithm was selected
the results open in ``SameBoardRunsWindow``, which only changes what is shown.
"""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox, QDialog, QGridLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel,
    QPushButton, QVBoxLayout, QWidget,
)

from same_board_algorithm_job import SameBoardAlgorithmQueue
from same_board_algorithms import ALGORITHMS, LABELS, LEGACY_PAIR, not_run, settings_for, support_reason
from same_board_comparison import HumanComparisonContext
from same_board_comparison_ui import SameBoardComparisonWindow
from same_board_execution_job import SameBoardExecutionJob
from same_board_runner import SameBoardExecution
from same_board_runs_ui import SameBoardRunsWindow


# The main window passes one of these English source descriptions; show them in
# Korean here (F-S4) without changing the main window. Other values pass through.
SOURCE_NAMES = {
    "currently loaded Replay": "현재 불러온 Replay",
    "completed current game": "방금 끝난 현재 판",
}
COMPLETED, CANCELLED = "완료", "취소됨"
CLOSE_RETRY = "결과 창을 닫지 못했습니다. 다시 닫아 주세요."


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
        self.setWindowTitle("같은 보드 비교")
        self.context = context
        self._active_token = None
        self._cancel_requested = False
        self._completed_execution = None
        self._result_window = None
        self._shutdown_started = False
        self._closed = False
        # Multi-algorithm state; all empty/None for the default existing pair.
        self._queue_algorithms = ()
        self._queue_token = None
        self._runs = {}
        self._runs_window = None
        self._r_target = None
        self.job = SameBoardExecutionJob(self)
        self.job.succeeded.connect(self._on_succeeded)
        self.job.failed.connect(self._on_failed)
        self.job.cancelled.connect(self._on_cancelled)
        self.queue = SameBoardAlgorithmQueue(self)
        self.queue.run_finished.connect(self._on_run_finished)
        self.queue.finished.connect(self._on_queue_finished)

        layout = QVBoxLayout(self)
        board = context.layout.board
        source = "가져온 완료 판 Human 기록 1개"
        if source_description:
            source += f"\n가져온 출처: {SOURCE_NAMES.get(source_description, source_description)}"
        self.source_label = QLabel(source)
        self.facts_label = QLabel(
            f"보드: {board.width} × {board.height} · 지뢰: {board.num_mines}\n"
            f"Human 최종 결과: {context.terminal_status.name} · "
            f"Human 기록 입력 수: {len(context.human_replay.events)}"
        )
        self.fingerprint_label = QLabel(f"배치 지문: {context.layout.board_fingerprint}")
        self.provenance_label = QLabel(
            "완료된 Human 판 기록으로 제출되었습니다. Human 표시, 제출 선언과 재구성 성공은 "
            "과거 입력이 모두 사람의 입력이었다는 증거가 아닙니다. 기록에 자동 입력이 "
            "섞여 있을 수 있습니다."
        )
        for label in (self.source_label, self.facts_label, self.fingerprint_label,
                      self.provenance_label):
            label.setTextFormat(Qt.PlainText)
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            layout.addWidget(label)
        self.algorithm_group = QGroupBox("실행할 알고리즘")
        selection = QGridLayout(self.algorithm_group)
        self.algorithm_checks = {}
        unsupported = None
        for index, key in enumerate(ALGORITHMS):
            check = QCheckBox(LABELS[key])
            check.setChecked(key in LEGACY_PAIR)
            reason = support_reason(key, board)
            if reason is not None:
                check.setEnabled(False)
                check.setToolTip(reason)
                unsupported = reason
            self.algorithm_checks[key] = check
            selection.addWidget(check, index // 3, index % 3)
        self.algorithm_checks["S4_R"].toggled.connect(self._on_r_toggled)
        self.selection_note = QLabel(
            "Stage 2와 Stage 3를 함께 고르면 기존 비교와 그 시간 재생 창을 씁니다. "
            "그 밖의 선택은 알고리즘별 한도(K 30초, Stage4 120초, Stage 2 / Stage 3 단독 120초) "
            "안에서 하나씩 차례로 실행합니다."
            + (f"\n{unsupported}" if unsupported else ""))
        self.selection_note.setTextFormat(Qt.PlainText)
        self.selection_note.setWordWrap(True)
        selection.addWidget(self.selection_note, (len(ALGORITHMS) + 2) // 3, 0, 1, 3)
        layout.addWidget(self.algorithm_group)
        controls = QHBoxLayout()
        self.run_button = QPushButton("실행")
        self.cancel_button = QPushButton("취소")
        self.open_result_button = QPushButton("결과 열기")
        self.run_button.clicked.connect(self._run)
        self.cancel_button.clicked.connect(self._cancel)
        self.open_result_button.clicked.connect(self._open_result)
        for button in (self.run_button, self.cancel_button, self.open_result_button):
            controls.addWidget(button)
        layout.addLayout(controls)
        self.status_label = QLabel("준비됨")
        self.status_label.setTextFormat(Qt.PlainText)
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.status_label)
        self._update_controls()
        self.resize(520, self.sizeHint().height())

    def _queue_busy(self):
        return self.queue is not None and (self.queue.state != "idle" or self._queue_token is not None)

    def _update_controls(self):
        available = not self._shutdown_started and not self._closed
        idle = self.job is not None and self.job.state == "idle" and not self._queue_busy()
        can_run = available and self._active_token is None and idle
        self.run_button.setEnabled(can_run)
        self.cancel_button.setEnabled(
            available and (self._active_token is not None or self._queue_busy())
            and not self._cancel_requested,
        )
        self.open_result_button.setEnabled(
            can_run and (self._completed_execution is not None or bool(self._runs)))
        self.algorithm_group.setEnabled(can_run)

    def selected_algorithms(self):
        return tuple(key for key in ALGORITHMS
                     if self.algorithm_checks[key].isEnabled() and self.algorithm_checks[key].isChecked())

    def _on_r_toggled(self, checked):
        check = self.algorithm_checks["S4_R"]
        if not checked:
            self._r_target = None
            check.setText(LABELS["S4_R"])
            return
        from stage4_live_contract import target_percent
        text, accepted = self._ask_r_target()
        try:
            if not accepted:
                raise ValueError("R 목표 입력을 취소했습니다.")
            target_percent(text)
        except Exception as exc:
            blocked = check.blockSignals(True)
            check.setChecked(False)
            check.blockSignals(blocked)
            self._r_target = None
            check.setText(LABELS["S4_R"])
            self.status_label.setText(f"Stage4 R을 선택하지 않음: {exc}")
            return
        self._r_target = text.strip()
        check.setText(f"{LABELS['S4_R']} (목표 {self._r_target}%)")

    def _r_target_dialog(self):
        """The R target entry dialog, with Korean title, prompt and buttons (F-S4)."""
        dialog = QInputDialog(self)
        dialog.setWindowTitle("Stage4 R 목표")
        dialog.setInputMode(QInputDialog.TextInput)
        dialog.setLabelText("R 목표 IOE를 양의 백분율로 입력하세요(필수, 추천값 없음):")
        dialog.setTextValue("")
        dialog.setOkButtonText("확인")
        dialog.setCancelButtonText("취소")
        return dialog

    def _ask_r_target(self):
        dialog = self._r_target_dialog()
        try:
            accepted = dialog.exec_() == QDialog.Accepted
            return dialog.textValue(), accepted
        finally:
            dialog.deleteLater()

    def _run(self):
        if (self._shutdown_started or self._closed or self._active_token is not None
                or self.job.state != "idle" or self._queue_busy()):
            return
        selected = self.selected_algorithms()
        if not selected:
            self.status_label.setText("실행할 알고리즘을 하나 이상 고르세요.")
            return
        legacy = all(key in selected for key in LEGACY_PAIR)
        queued = tuple(key for key in selected if not (legacy and key in LEGACY_PAIR))
        if not self._close_result() or not self._close_runs():
            return
        self._completed_execution = None
        self._cancel_requested = False
        self._runs = {}
        self._queue_algorithms = queued
        if not legacy:
            self._start_queue()
            self._update_controls()
            return
        try:
            # The accepted job reports even startup failures after returning a token.
            self._active_token = self.job.start(self.context)
        except Exception as exc:
            self.status_label.setText(f"시작 실패: {exc}")
            if queued:
                self._record_legacy("ERROR", f"시작 실패: {exc}")
                self._start_queue()
        else:
            self.status_label.setText("실행 중")
        self._update_controls()

    def _record_legacy(self, outcome, detail):
        for key in LEGACY_PAIR:
            self._runs[key] = not_run(key, outcome, detail, settings=settings_for(key))

    def _start_queue(self):
        if self._cancel_requested:
            for key in self._queue_algorithms:
                self._runs[key] = not_run(key, "CANCELLED", "시작 전에 취소됨.",
                                          settings=settings_for(key, self._r_target if key == "S4_R" else None))
            self._finish_comparison(CANCELLED)
            return
        try:
            self._queue_token = self.queue.start(self.context.layout.board, self._queue_algorithms,
                                                 self._r_target)
        except Exception as exc:
            for key in self._queue_algorithms:
                self._runs[key] = not_run(key, "ERROR", f"시작 실패: {exc}")
            self._finish_comparison(f"시작 실패: {exc}")
            return
        if self._queue_token is not None and self.queue.current_algorithm is not None:
            self.status_label.setText(f"{LABELS[self.queue.current_algorithm]} 실행 중")

    def _on_run_finished(self, token, run):
        if self._shutdown_started or self._closed or token != self._queue_token:
            return
        self._runs[run.algorithm] = run
        current = self.queue.current_algorithm
        self.status_label.setText(f"{run.label}: {run.outcome}"
                                  + (f" · {LABELS[current]} 실행 중" if current else ""))

    def _on_queue_finished(self, token):
        if self._shutdown_started or self._closed or token != self._queue_token:
            return
        self._queue_token = None
        self._finish_comparison(CANCELLED if self._cancel_requested else COMPLETED)

    def _finish_comparison(self, prefix):
        self._queue_token = None
        self._cancel_requested = False
        summary = "; ".join(f"{LABELS[key]}: {self._runs[key].outcome}"
                            for key in ALGORITHMS if key in self._runs)
        if self._completed_execution is not None:
            execution = self._completed_execution
            summary = (f"Stage 2: {execution.stage2_metrics.outcome.name}; "
                       f"Stage 3: {execution.stage3_metrics.outcome.name}"
                       + (f"; {summary}" if summary else ""))
        self.status_label.setText(f"{prefix} — {summary}")
        self._update_controls()
        if prefix == COMPLETED and (self._runs or self._completed_execution is not None):
            self._open_result()

    def _cancel(self):
        if (self._shutdown_started or self._closed or self._cancel_requested):
            return
        if self._active_token is None and self._queue_busy():
            self._cancel_requested = True
            self.status_label.setText("취소 중")
            self._update_controls()
            self.queue.cancel()
            return
        if self._active_token is None:
            return
        # Set intent first: coincident success must not attach a result.
        self._cancel_requested = True
        self.status_label.setText("취소 중")
        self._update_controls()
        try:
            self.job.cancel()
        except Exception as exc:
            self.status_label.setText(f"취소 요청 실패: {exc}")

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
            self._on_failed(token, "비교 결과 형식 또는 가져온 판 정보의 동일성이 맞지 않습니다.")
            return
        self._active_token = None
        self._cancel_requested = False
        self._completed_execution = execution
        if self._queue_algorithms:
            self.status_label.setText("Stage 2 / Stage 3 완료")
            self._start_queue()
            self._update_controls()
            return
        self.status_label.setText(
            f"{COMPLETED} — Stage 2: {execution.stage2_metrics.outcome.name}; "
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
        self.status_label.setText(f"실패: {diagnostic}")
        if self._queue_algorithms:
            self._record_legacy("ERROR", f"실패: {diagnostic}")
            self._start_queue()
        self._update_controls()

    def _on_cancelled(self, token):
        if not self._matches_active_token(token):
            return
        cancelled_queue = bool(self._queue_algorithms)
        self._active_token = None
        self._completed_execution = None
        if cancelled_queue:
            self._record_legacy("CANCELLED", "실행 중 취소됨.")
            self._start_queue()  # Records every queued algorithm as CANCELLED.
            return
        self._cancel_requested = False
        self.status_label.setText(CANCELLED)
        self._update_controls()

    def _open_result(self):
        if self._queue_algorithms:
            self._open_runs()
            return
        if (self._shutdown_started or self._closed or self._active_token is not None
                or self.job.state != "idle" or self._completed_execution is None):
            return
        if self._result_window is None:
            try:
                viewer = SameBoardComparisonWindow(self._completed_execution, self)
            except Exception as exc:
                self.status_label.setText(f"결과 창 열기 실패: {exc}")
                return
            self._result_window = viewer
            viewer.closed.connect(self._on_result_closed)
        self._result_window.show()
        self._result_window.raise_()
        self._result_window.activateWindow()

    def _on_result_closed(self):
        if self.sender() is self._result_window:
            self._result_window = None

    def _open_runs(self):
        if (self._shutdown_started or self._closed or self._active_token is not None
                or self.job.state != "idle" or self._queue_busy()
                or not (self._runs or self._completed_execution is not None)):
            return
        if self._runs_window is None:
            try:
                viewer = SameBoardRunsWindow(self.context, dict(self._runs), self._completed_execution, self)
            except Exception as exc:
                self.status_label.setText(f"결과 창 열기 실패: {exc}")
                return
            self._runs_window = viewer
            viewer.closed.connect(self._on_runs_closed)
            viewer.legacy_requested.connect(self._open_legacy_detail)
        self._runs_window.show()
        self._runs_window.raise_()
        self._runs_window.activateWindow()

    def _open_legacy_detail(self):
        if self._completed_execution is None or self._shutdown_started or self._closed:
            return
        if self._result_window is None:
            try:
                viewer = SameBoardComparisonWindow(self._completed_execution, self)
            except Exception as exc:
                self.status_label.setText(f"결과 창 열기 실패: {exc}")
                return
            self._result_window = viewer
            viewer.closed.connect(self._on_result_closed)
        self._result_window.show()
        self._result_window.raise_()
        self._result_window.activateWindow()

    def _on_runs_closed(self):
        if self.sender() is self._runs_window:
            self._runs_window = None

    def _close_runs(self):
        viewer = self._runs_window
        if viewer is not None:
            if not viewer.close():
                self.status_label.setText(CLOSE_RETRY)
                return False
            self._runs_window = None
        return True

    def _close_result(self):
        viewer = self._result_window
        if viewer is not None:
            if not viewer.close():
                self.status_label.setText(CLOSE_RETRY)
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
            if self.queue is not None:
                self.queue.shutdown()
        except Exception as exc:
            self.status_label.setText(f"닫기·종료 실패: {exc}. 다시 닫아 주세요.")
            event.ignore()
            return
        if not self._close_result() or not self._close_runs():
            event.ignore()
            return
        self.job = None
        self.queue = None
        self._queue_token = None
        self._runs = {}
        self._active_token = None
        self._completed_execution = None
        self._closed = True
        self._update_controls()
        self.closed.emit()
