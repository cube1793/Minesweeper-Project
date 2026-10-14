"""Read-only Qt presentation of one already-computed Stage-3 V1 execution.

Only the trace player reconstructs game state. This window owns presentation
widgets and an index timer; recorded modeled microseconds are never scheduled.
"""

from PyQt5.QtCore import QPointF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSlider,
    QSpinBox, QStyle, QStyleOptionSlider, QVBoxLayout, QWidget,
)

from core_engine import CellState
from stage3_execution import Stage3Execution
import stage3_identity
import stage3_physical
from stage3_trace_player import Stage3TracePlayer


CELL_SIZE = 28
STAGE3_PRESENTATION_INTERVAL_MIN_MS = 20
STAGE3_PRESENTATION_INTERVAL_MAX_MS = 5000
STAGE3_PRESENTATION_INTERVAL_DEFAULT_MS = 200
NUMBER_COLORS = {
    1: "#0000ff", 2: "#008000", 3: "#ff0000", 4: "#000080",
    5: "#800000", 6: "#008080", 7: "#000000", 8: "#808080",
}
MOVEMENT_LEGEND = (
    "Blue ring: cursor • Orange outline: action target • Line: modeled "
    "cell-to-cell displacement, not a continuous OS mouse trajectory."
)


class Stage3VisualizerCell(QLabel):
    """A public observation value, with no input or hidden-board access."""

    def __init__(self, x: int, y: int, parent=None):
        super().__init__(parent)
        self.coordinate = (x, y)
        self.setFixedSize(CELL_SIZE, CELL_SIZE)
        self.setAlignment(Qt.AlignCenter)
        self.setFont(QFont("Arial", 14, QFont.Bold))
        self.render_state(CellState.HIDDEN)

    def render_state(self, value: int):
        self.logical_state = value
        background, color = "#c0c0c0", "#000000"
        border = "2px outset #ffffff"
        if value == CellState.HIDDEN:
            text, description = "", "HIDDEN"
        elif value == CellState.FLAGGED:
            text, description, color = "⚑", "FLAGGED", "#c00000"
        elif value == CellState.EXPLODED:
            text, description, background = "✹", "EXPLODED", "#ff5555"
            border = "1px solid #a0a0a0"
        elif value == CellState.MINE:
            text, description = "✹", "MINE"
            border = "1px solid #a0a0a0"
        elif value == CellState.FALSE_FLAG:
            text, description, color = "×", "FALSE_FLAG", "#c00000"
            background, border = "#e0e0e0", "1px solid #a0a0a0"
        elif 0 <= value <= 8:
            text, description = "" if value == 0 else str(value), f"Revealed {value}"
            color, background = NUMBER_COLORS.get(value, "#000000"), "#e0e0e0"
            border = "1px solid #a0a0a0"
        else:
            raise ValueError(f"Unsupported public cell state: {value}")
        self.setText(text)
        self.setToolTip(f"{self.coordinate}: {description}")
        self.setAccessibleName(self.toolTip())
        self.setStyleSheet(
            "QLabel {"
            f" background-color: {background}; color: {color}; border: {border};"
            " margin: 0px; padding: 0px; }"
        )


class _MovementOverlay(QWidget):
    """Presentation coordinates only; no interpolation or engine ownership."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.current_cursor = (0, 0)
        self.movement_start = None
        self.action_target = None

    @property
    def movement_line(self):
        if self.movement_start is None or self.movement_start == self.action_target:
            return None
        return self.movement_start, self.action_target

    def set_trace(self, trace, cursor):
        self.current_cursor = cursor
        self.movement_start = None if trace is None else trace.cursor_before
        self.action_target = None if trace is None else (trace.move.x, trace.move.y)
        self.update()

    @staticmethod
    def cell_center(coordinate):
        x, y = coordinate
        return QPointF((x + 0.5) * CELL_SIZE, (y + 0.5) * CELL_SIZE)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(Qt.NoBrush)
        if self.movement_line is not None:
            start, end = map(self.cell_center, self.movement_line)
            # A white underlay keeps the modeled displacement visible on clues.
            painter.setPen(QPen(QColor("#ffffff"), 4))
            painter.drawLine(start, end)
            painter.setPen(QPen(QColor("#2463c5"), 2))
            painter.drawLine(start, end)
        if self.action_target is not None:
            x, y = self.action_target
            painter.setPen(QPen(QColor("#cc7000"), 2))
            painter.drawRect(x * CELL_SIZE + 2, y * CELL_SIZE + 2,
                             CELL_SIZE - 4, CELL_SIZE - 4)
        painter.setPen(QPen(QColor("#2463c5"), 2))
        painter.drawEllipse(self.cell_center(self.current_cursor), 9, 9)


class _IndexSlider(QSlider):
    """Local handle-aware track seeking; native Qt still handles dragging."""

    trackPressed = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            option = QStyleOptionSlider()
            self.initStyleOption(option)
            handle = self.style().subControlRect(
                QStyle.CC_Slider, option, QStyle.SC_SliderHandle, self,
            )
            if not handle.contains(event.pos()):
                span = max(1, self.width() - handle.width())
                position = max(0, min(span, event.x() - handle.width() // 2))
                self.trackPressed.emit()
                self.setValue(QStyle.sliderValueFromPosition(
                    self.minimum(), self.maximum(), position, span, option.upsideDown,
                ))
                event.accept()
                return
        super().mousePressEvent(event)


class Stage3VisualizerWindow(QWidget):
    """A separate window with its own player for one immutable execution."""

    closed = pyqtSignal()

    def __init__(self, execution: Stage3Execution, parent=None):
        super().__init__(parent, Qt.Window)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle("Stage-3 Visualizer")
        self.player = Stage3TracePlayer(execution)
        self._closed = False
        self.timer = QTimer(self)
        self.timer.setInterval(STAGE3_PRESENTATION_INTERVAL_DEFAULT_MS)
        self.timer.timeout.connect(self._advance_autoplay)
        layout = QVBoxLayout(self)

        self.title_label = QLabel("Stage-3 Visualizer")
        self.title_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(self.title_label)
        identities = QHBoxLayout()
        self.algorithm_label = QLabel(
            f"Algorithm: Stage-3 V{stage3_identity.STAGE3_V1_IDENTITY.algorithm_spec_version}"
        )
        self.physical_label = QLabel(
            f"Physical: {stage3_physical.MODEL_C_DISPLAY_NAME} · "
            f"profile v{stage3_physical.MODEL_C_V1_IDENTITY.physical_profile_version}"
        )
        identities.addWidget(self.algorithm_label)
        identities.addWidget(self.physical_label)
        identities.addStretch()
        layout.addLayout(identities)
        self.identity_label = QLabel(
            f"Benchmark: {execution.spec.benchmark_set_id} • "
            f"Game index: {execution.board.game_index} • "
            f"Final result: {execution.result.status.name}"
        )
        self.identity_label.setTextFormat(Qt.PlainText)
        self.identity_label.setWordWrap(True)
        layout.addWidget(self.identity_label)
        self.fingerprint_label = QLabel(f"Board fingerprint: {execution.board.board_fingerprint}")
        self.fingerprint_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.fingerprint_label.setWordWrap(True)
        self.fingerprint_label.setToolTip("Evaluation identity only; never solver evidence.")
        layout.addWidget(self.fingerprint_label)
        self.status_label = QLabel()
        layout.addWidget(self.status_label)

        self.board_container = QWidget()
        grid = QGridLayout(self.board_container)
        grid.setSpacing(0)
        grid.setContentsMargins(0, 0, 0, 0)
        self.cells = {}
        for y, row in enumerate(self.player.get_observation()):
            for x, value in enumerate(row):
                cell = Stage3VisualizerCell(x, y, self.board_container)
                self.cells[(x, y)] = cell
                grid.addWidget(cell, y, x)
        self.board_container.setFixedSize(
            execution.spec.width * CELL_SIZE, execution.spec.height * CELL_SIZE,
        )
        self.overlay = _MovementOverlay(self.board_container)
        self.overlay.setGeometry(self.board_container.rect())
        self.overlay.raise_()
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.board_container)
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(self.scroll_area, 1)
        self.legend_label = QLabel(MOVEMENT_LEGEND)
        self.legend_label.setWordWrap(True)
        layout.addWidget(self.legend_label)

        controls = QHBoxLayout()
        for name, text, icon, handler in (
            ("first_button", "First", QStyle.SP_MediaSkipBackward, self.on_first),
            ("previous_button", "Previous", QStyle.SP_MediaSeekBackward, self.on_previous),
            ("play_button", "Play", QStyle.SP_MediaPlay, self.on_play_pause),
            ("next_button", "Next", QStyle.SP_MediaSeekForward, self.on_next),
            ("last_button", "Last", QStyle.SP_MediaSkipForward, self.on_last),
        ):
            button = QPushButton(text)
            button.setIcon(self.style().standardIcon(icon))
            button.clicked.connect(handler)
            setattr(self, name, button)
            controls.addWidget(button)
        controls.addStretch()
        layout.addLayout(controls)

        position = QHBoxLayout()
        self.slider = _IndexSlider(Qt.Horizontal)
        self.slider.setAccessibleName("Stage-3 trace index")
        self.slider.valueChanged.connect(self.on_slider_changed)
        self.slider.sliderPressed.connect(self._stop_autoplay)
        self.slider.trackPressed.connect(self._stop_autoplay)
        position.addWidget(self.slider, 1)
        self.step_label = QLabel()
        position.addWidget(self.step_label)
        layout.addLayout(position)

        interval = QHBoxLayout()
        self.playback_label = QLabel()
        interval.addWidget(self.playback_label)
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(
            STAGE3_PRESENTATION_INTERVAL_MIN_MS, STAGE3_PRESENTATION_INTERVAL_MAX_MS,
        )
        self.interval_spin.setValue(STAGE3_PRESENTATION_INTERVAL_DEFAULT_MS)
        self.interval_spin.setSuffix(" ms/step")
        self.interval_spin.setToolTip("Presentation interval only; recorded modeled time is unchanged.")
        self.interval_spin.valueChanged.connect(self.timer.setInterval)
        self.interval_spin.valueChanged.connect(self._update_playback_label)
        self._update_playback_label()
        interval.addWidget(self.interval_spin)
        interval.addStretch()
        layout.addLayout(interval)

        details = QGridLayout()
        self.detail_labels = {}
        for index, (key, caption) in enumerate((
            ("action", "Physical action"), ("target", "Target (x, y; zero-based)"),
            ("movement", "Cursor before → target"), ("status_after", "Status after action"),
            ("modeled_action_us", "Action modeled time"),
            ("cumulative_modeled_us", "Cumulative modeled time"),
            ("total_modeled_us", "Total modeled time"),
            ("safe_cells_opened_delta", "Safe cells opened delta"),
            ("explicit_flag_delta", "Explicit flag delta"),
        )):
            row, column = divmod(index, 2)
            details.addWidget(QLabel(caption + ":"), row, column * 2)
            label = QLabel()
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.detail_labels[key] = label
            details.addWidget(label, row, column * 2 + 1)
        layout.addLayout(details)
        self.refresh()
        # Leave scrolling available on smaller screens, with fixed-size cells.
        available = self.screen().availableGeometry()
        self.resize(min(max(820, self.board_container.width() + 48), available.width()),
                    min(self.board_container.height() + 410, available.height()))

    def _update_playback_label(self):
        self.playback_label.setText(
            f"Playback: Index · {self.interval_spin.value()} ms/step (presentation)"
        )

    def refresh(self):
        player = self.player
        for y, row in enumerate(player.get_observation()):
            for x, value in enumerate(row):
                self.cells[(x, y)].render_state(value)
        trace = player.current_trace
        self.overlay.set_trace(trace, player.current_cursor)
        index, count = player.current_index, player.step_count
        self.step_label.setText(f"Step {index} / {count}")
        self.status_label.setText(f"Current reconstructed status: {player.status.name}")
        values = {
            "cumulative_modeled_us": f"{player.cumulative_modeled_us:,} µs",
            "total_modeled_us": f"{player.execution.result.total_modeled_us:,} µs",
        }
        if trace is not None:
            target = (trace.move.x, trace.move.y)
            values.update({
                "action": trace.move.action.name,
                "target": str(target),
                "movement": f"{trace.cursor_before} → {target}",
                "modeled_action_us": f"{trace.modeled_action_us:,} µs",
                "status_after": trace.status_after.name,
                "safe_cells_opened_delta": str(trace.safe_cells_opened_delta),
                "explicit_flag_delta": str(trace.explicit_flag_delta),
            })
        for key, label in self.detail_labels.items():
            label.setText(values.get(key, "—"))
        previous_block = self.slider.blockSignals(True)
        try:
            self.slider.setRange(0, count)
            self.slider.setValue(index)
            self.slider.setEnabled(count > 0)
        finally:
            self.slider.blockSignals(previous_block)
        self.first_button.setEnabled(index > 0)
        self.previous_button.setEnabled(index > 0)
        self.next_button.setEnabled(index < count)
        self.last_button.setEnabled(index < count)
        self.play_button.setEnabled(index < count)
        if index == count:
            self._stop_autoplay()

    def _stop_autoplay(self):
        self.timer.stop()
        self.play_button.setText("Play")
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

    def on_first(self):
        self._stop_autoplay()
        self.player.go_to(0)
        self.refresh()

    def on_previous(self):
        self._stop_autoplay()
        self.player.previous()
        self.refresh()

    def on_next(self):
        self._stop_autoplay()
        self.player.next()
        self.refresh()

    def on_last(self):
        self._stop_autoplay()
        self.player.go_to(self.player.step_count)
        self.refresh()

    def on_slider_changed(self, index: int):
        self._stop_autoplay()
        self.player.go_to(index)
        self.refresh()

    def on_play_pause(self):
        if self.timer.isActive():
            self._stop_autoplay()
        elif not self._closed and self.player.current_index < self.player.step_count:
            self.timer.start()
            self.play_button.setText("Pause")
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))

    def _advance_autoplay(self):
        if not self.timer.isActive():
            return
        self.player.next()
        self.refresh()

    def closeEvent(self, event):
        super().closeEvent(event)
        if event.isAccepted():
            self._stop_autoplay()
            if not self._closed:
                self._closed = True
                self.closed.emit()
