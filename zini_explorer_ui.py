"""Qt presentation of an already built ZiNi trace, by logical step index.

The main UI owns eligibility, lazy trace construction, and session lifetime.
This window only reads the controller and delegates navigation to it. Closing
the window leaves the cached trace and the controller's current index intact.
"""

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSlider,
    QSpinBox, QStyle, QVBoxLayout, QWidget,
)

from zini_explorer import ZiniExplorerController
from zini_trace import ZiniTraceSelection


# Keep the classic board palette without importing the engine-bound main UI.
NUMBER_COLORS = {
    1: "#0000FF", 2: "#008000", 3: "#FF0000", 4: "#000080",
    5: "#800000", 6: "#008080", 7: "#000000", 8: "#808080",
}
CELL_SIZE = 28
SELECTION_TEXT = {
    ZiniTraceSelection.GREEDY: "현재 상태 기준 greedy",
    ZiniTraceSelection.MAX_TIE_ALT: "현재 상태 기준 최대 Premium 동률",
    ZiniTraceSelection.BELOW_MAX: "현재 상태 기준 최대 Premium 미만",
    ZiniTraceSelection.FALLBACK_GREEDY: "현재 상태 기준 첫 fallback",
    ZiniTraceSelection.FALLBACK_ALT: "현재 상태 기준 다른 fallback",
}


class ZiniExplorerCell(QLabel):
    """Read-only cell with independent base state and step overlays."""

    def __init__(self, x: int, y: int, parent=None):
        super().__init__(parent)
        self.setFixedSize(CELL_SIZE, CELL_SIZE)
        self.setAlignment(Qt.AlignCenter)
        self.setFont(QFont("Arial", 14, QFont.Bold))
        self.setToolTip(f"({x}, {y})")
        self.render_state("closed")

    def render_state(self, state: str, value: int = 0, *, selected: bool = False,
                     newly_revealed: bool = False, newly_flagged: bool = False):
        self.state = state
        self.selected = selected
        self.newly_revealed = newly_revealed
        self.newly_flagged = newly_flagged
        for name in ("state", "selected", "newly_revealed", "newly_flagged"):
            self.setProperty(name, getattr(self, name))

        if state == "flagged":
            text, color = "🚩", "#c00000"
        elif state == "revealed":
            text = "" if value == 0 else str(value)
            color = NUMBER_COLORS.get(value, "#000000")
        else:
            text, color = "", "#000000"
        self.setText(text)

        background = "#e0e0e0" if state == "revealed" else "#c0c0c0"
        if newly_revealed:
            background = "#d8f0dd"
        if newly_flagged:
            background = "#ffe2a8"
        border = (
            "2px solid #2463c5" if selected else
            "1px solid #a0a0a0" if state == "revealed" else
            "2px outset #ffffff"
        )
        self.setStyleSheet(
            "QLabel {"
            f" background-color: {background}; color: {color}; border: {border};"
            " margin: 0px; padding: 0px; }"
        )


class ZiniExplorerWindow(QWidget):
    """Separate Index-only view of one trace-ready controller session.

    Construction never requests a trace. Reopening a valid cached session
    preserves its logical index; only the autoplay timer belongs to this view.
    """

    closed = pyqtSignal()

    def __init__(self, controller: ZiniExplorerController, parent=None):
        if (controller.state != "ready" or controller.trace is None
                or controller.snapshot is None or controller.current_index is None):
            raise ValueError("ZiNi Explorer requires an eligible, trace-ready controller.")
        super().__init__(parent, Qt.Window)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.controller = controller
        self._session_token = controller.token
        self.setWindowTitle("ZiNi Explorer")
        self.resize(780, 700)

        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self._advance_autoplay)
        layout = QVBoxLayout(self)

        counts = QHBoxLayout()
        self.step_label = QLabel()
        self.clicks_label = QLabel()
        for label in (self.step_label, self.clicks_label):
            label.setFont(QFont("Arial", 12, QFont.Bold))
            counts.addWidget(label)
            counts.addSpacing(18)
        counts.addStretch()
        layout.addLayout(counts)
        explanation = QLabel("Step: 논리 결정 단계  ·  Clicks: 누적 물리 클릭 수")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        self.board_container = QWidget()
        grid = QGridLayout(self.board_container)
        grid.setSpacing(0)
        grid.setContentsMargins(0, 0, 0, 0)
        snapshot = controller.snapshot
        self.cells = {}
        for y in range(snapshot.height):
            for x in range(snapshot.width):
                cell = ZiniExplorerCell(x, y, self.board_container)
                self.cells[(x, y)] = cell
                grid.addWidget(cell, y, x)
        self.board_container.setFixedSize(
            snapshot.width * CELL_SIZE, snapshot.height * CELL_SIZE,
        )
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.board_container)
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(self.scroll_area, 1)

        legend = QHBoxLayout()
        for text, style in (
            ("선택 좌표", "border: 2px solid #2463c5;"),
            ("새로 열린 칸", "background-color: #d8f0dd;"),
            ("새로 놓은 깃발", "background-color: #ffe2a8;"),
        ):
            label = QLabel(text)
            label.setStyleSheet(f"QLabel {{ {style} padding: 3px; }}")
            legend.addWidget(label)
        legend.addStretch()
        layout.addLayout(legend)

        controls = QHBoxLayout()
        button_specs = (
            ("first_button", QStyle.SP_MediaSkipBackward, "처음", self.on_first),
            ("previous_button", QStyle.SP_MediaSeekBackward, "이전 단계", self.on_previous),
            ("play_button", QStyle.SP_MediaPlay, "재생", self.on_play_pause),
            ("next_button", QStyle.SP_MediaSeekForward, "다음 단계", self.on_next),
            ("last_button", QStyle.SP_MediaSkipForward, "마지막", self.on_last),
        )
        for name, icon, tooltip, handler in button_specs:
            button = QPushButton()
            button.setIcon(self.style().standardIcon(icon))
            button.setToolTip(tooltip)
            button.setAccessibleName(tooltip)
            button.setFocusPolicy(Qt.NoFocus)
            button.setFixedSize(36, 30)
            button.clicked.connect(handler)
            setattr(self, name, button)
            controls.addWidget(button)
        controls.addStretch()
        controls.addWidget(QLabel("Index 간격"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(20, 5000)
        self.interval_spin.setValue(200)
        self.interval_spin.setSuffix(" ms/step")
        self.interval_spin.setToolTip("논리 단계당 자동 재생 간격")
        self.interval_spin.valueChanged.connect(self.timer.setInterval)
        controls.addWidget(self.interval_spin)
        layout.addLayout(controls)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setAccessibleName("논리 단계 Index")
        self.slider.valueChanged.connect(self.on_slider_changed)
        self.slider.sliderPressed.connect(self._stop_autoplay)
        layout.addWidget(self.slider)

        self.diagnostic_labels = {}
        self.diagnostic_rows = {}
        for key, caption in (
            ("action", "Action"),
            ("coordinate", "좌표 (x, y; 0부터)"),
            ("premium", "Move Premium"),
            ("best_premium", "적용 전 최대 Premium"),
            ("selection", "선택 관계 (적용 전 상태)"),
            ("newly_revealed", "새로 열린 칸"),
            ("newly_flagged", "새로 놓은 깃발"),
            ("tie_count", "최대 Premium 숫자 칸 동률 수"),
        ):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            caption_label = QLabel(caption)
            caption_label.setMinimumWidth(215)
            row_layout.addWidget(caption_label)
            value_label = QLabel("—")
            value_label.setWordWrap(True)
            row_layout.addWidget(value_label, 1)
            self.diagnostic_labels[key] = value_label
            self.diagnostic_rows[key] = row
            layout.addWidget(row)
        self.refresh()

    def _session_ready(self) -> bool:
        return (
            self.controller.token == self._session_token
            and self.controller.state == "ready"
            and self.controller.trace is not None
            and self.controller.snapshot is not None
            and self.controller.current_index is not None
        )

    def refresh(self):
        """Render only the controller's exposed snapshot, state, and current step."""
        ready = self._session_ready()
        snapshot = self.controller.snapshot if ready else None
        step = self.controller.current_step if ready else None
        revealed = self.controller.revealed if ready else frozenset()
        flagged = self.controller.flagged_mines if ready else frozenset()
        newly_revealed = frozenset(step.newly_revealed) if step else frozenset()
        newly_flagged = frozenset(step.newly_flagged) if step else frozenset()
        selected = (step.move.x, step.move.y) if step else None
        for coordinate, cell in self.cells.items():
            x, y = coordinate
            state = (
                "flagged" if coordinate in flagged else
                "revealed" if coordinate in revealed else "closed"
            )
            value = snapshot.adjacent[y][x] if state == "revealed" else 0
            cell.render_state(
                state, value, selected=coordinate == selected,
                newly_revealed=coordinate in newly_revealed,
                newly_flagged=coordinate in newly_flagged,
            )

        index = self.controller.current_index if ready else 0
        count = self.controller.step_count if ready else 0
        if not ready or index == count:
            self._stop_autoplay()
        self.step_label.setText(f"Step {index} / {count}" if ready else "Step — / —")
        self.clicks_label.setText(
            f"Clicks {self.controller.cumulative_clicks} / {self.controller.clicks}"
            if ready else "Clicks — / —"
        )
        values = {}
        if step is not None:
            values = {
                "action": step.move.action,
                "coordinate": f"({step.move.x}, {step.move.y})",
                "premium": step.move.premium,
                "best_premium": step.best_premium,
                "selection": SELECTION_TEXT[step.selection],
                "newly_revealed": len(step.newly_revealed),
                "newly_flagged": len(step.newly_flagged),
                "tie_count": step.tie_count,
            }
        for key, label in self.diagnostic_labels.items():
            value = values.get(key)
            label.setText("—" if value is None else str(value))
        show_ties = step is not None and step.move.action != "fallback_click"
        self.diagnostic_rows["tie_count"].setVisible(show_ties)
        self.diagnostic_labels["tie_count"].setVisible(show_ties)

        previous_block = self.slider.blockSignals(True)
        try:
            self.slider.setRange(0, count)
            self.slider.setValue(index)
            self.slider.setEnabled(ready and count > 0)
        finally:
            self.slider.blockSignals(previous_block)
        self.first_button.setEnabled(ready and index > 0)
        self.previous_button.setEnabled(ready and index > 0)
        self.next_button.setEnabled(ready and index < count)
        self.last_button.setEnabled(ready and index < count)
        self.play_button.setEnabled(ready and index < count)

    def _stop_autoplay(self):
        self.timer.stop()
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_button.setToolTip("재생")
        self.play_button.setAccessibleName("재생")

    def on_first(self):
        self._stop_autoplay()
        if self._session_ready():
            self.controller.go_to(0)
        self.refresh()

    def on_previous(self):
        self._stop_autoplay()
        if self._session_ready():
            self.controller.previous()
        self.refresh()

    def on_next(self):
        self._stop_autoplay()
        if self._session_ready():
            self.controller.next()
        self.refresh()

    def on_last(self):
        self._stop_autoplay()
        if self._session_ready():
            self.controller.go_to(self.controller.step_count)
        self.refresh()

    def on_slider_changed(self, index: int):
        self._stop_autoplay()
        if self._session_ready():
            self.controller.go_to(index)
        self.refresh()

    def on_play_pause(self):
        if self.timer.isActive():
            self._stop_autoplay()
        elif (self._session_ready()
              and self.controller.current_index < self.controller.step_count):
            self.timer.start(self.interval_spin.value())
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
            self.play_button.setToolTip("일시 정지")
            self.play_button.setAccessibleName("일시 정지")

    def _advance_autoplay(self):
        if not self.timer.isActive():
            return
        if self._session_ready():
            self.controller.next()
        self.refresh()

    def closeEvent(self, event):
        self._stop_autoplay()
        super().closeEvent(event)
        if event.isAccepted():
            self.closed.emit()
