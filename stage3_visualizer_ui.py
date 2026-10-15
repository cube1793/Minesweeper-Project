"""Read-only Qt presentation of one already-computed Stage-3 V1 execution.

Only the trace player reconstructs game state. This window owns presentation
widgets, frame requests and synthetic cursor geometry. Recorded modeled time
is advanced only by the pure modeled playback controller.
"""

from PyQt5.QtCore import QPointF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import (
    QComboBox, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSlider,
    QSpinBox, QStyle, QStyleOptionSlider, QVBoxLayout, QWidget,
)

from core_engine import CellState
from stage3_execution import Stage3Execution
import stage3_identity
import stage3_physical
from stage3_trace_player import Stage3TracePlayer
from stage3_modeled_playback import SUPPORTED_SPEEDS, Stage3ModeledPlayback


CELL_SIZE = 28
STAGE3_PRESENTATION_INTERVAL_MIN_MS = 20
STAGE3_PRESENTATION_INTERVAL_MAX_MS = 5000
STAGE3_PRESENTATION_INTERVAL_DEFAULT_MS = 200
STAGE3_MODELED_FRAME_INTERVAL_MS = 16
NUMBER_COLORS = {
    1: "#0000ff", 2: "#008000", 3: "#ff0000", 4: "#000080",
    5: "#800000", 6: "#008080", 7: "#000000", 8: "#808080",
}
MOVEMENT_LEGEND = (
    "Blue ring: cursor • Orange outline: action target • Line: modeled "
    "cell-to-cell displacement, not a continuous OS mouse trajectory."
)

MODELED_MOVEMENT_LEGEND = (
    "Blue ring: synthetic cursor • Orange outline: pending action target • "
    "Straight path with presentation easing, not a continuous OS mouse trajectory."
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
    """Static trace coordinates plus an optional synthetic presentation position."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.current_cursor = (0, 0)
        self.movement_start = None
        self.action_target = None
        self.presentation_position = None

    @property
    def movement_line(self):
        if self.movement_start is None or self.movement_start == self.action_target:
            return None
        return self.movement_start, self.action_target

    def set_trace(self, trace, cursor):
        self.current_cursor = cursor
        self.movement_start = None if trace is None else trace.cursor_before
        self.action_target = None if trace is None else (trace.move.x, trace.move.y)
        self.presentation_position = None
        self.update()

    def set_pending(self, trace, cursor, progress):
        self.current_cursor = cursor
        self.movement_start = trace.cursor_before
        self.action_target = (trace.move.x, trace.move.y)
        self.presentation_position = self.interpolated_center(
            self.movement_start, self.action_target, progress,
        )
        self.update()

    @classmethod
    def interpolated_center(cls, start, target, progress):
        # Fraction -> float only at the rendering edge; never fed back to timing.
        u = float(progress)
        q = u * u * (3 - 2 * u)
        a, b = cls.cell_center(start), cls.cell_center(target)
        return a + (b - a) * q

    @property
    def cursor_center(self):
        if self.presentation_position is not None:
            return self.presentation_position
        return self.cell_center(self.current_cursor)

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
        painter.drawEllipse(self.cursor_center, 9, 9)


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

    def __init__(self, execution: Stage3Execution, parent=None, *, clock=None):
        super().__init__(parent, Qt.Window)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle("Stage-3 Visualizer")
        self.player = Stage3TracePlayer(execution)
        self.modeled_playback = (
            Stage3ModeledPlayback(self.player) if clock is None
            else Stage3ModeledPlayback(self.player, clock=clock)
        )
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
        self.error_label = QLabel()
        self.error_label.setTextFormat(Qt.PlainText)
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #c00000;")
        self.error_label.hide()
        layout.addWidget(self.error_label)

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
        self.slider.sliderPressed.connect(self._cancel_partial)
        self.slider.trackPressed.connect(self._cancel_partial)
        position.addWidget(self.slider, 1)
        self.step_label = QLabel()
        position.addWidget(self.step_label)
        layout.addLayout(position)

        interval = QHBoxLayout()
        interval.addWidget(QLabel("Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(("Index", "Modeled-Time"))
        self.mode_combo.setAccessibleName("Playback mode")
        interval.addWidget(self.mode_combo)
        interval.addWidget(QLabel("Index interval:"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(
            STAGE3_PRESENTATION_INTERVAL_MIN_MS, STAGE3_PRESENTATION_INTERVAL_MAX_MS,
        )
        self.interval_spin.setValue(STAGE3_PRESENTATION_INTERVAL_DEFAULT_MS)
        self.interval_spin.setSuffix(" ms/step")
        self.interval_spin.setToolTip("Presentation interval only; recorded modeled time is unchanged.")
        self.interval_spin.valueChanged.connect(self._on_interval_changed)
        interval.addWidget(self.interval_spin)
        interval.addWidget(QLabel("Modeled speed:"))
        self.speed_combo = QComboBox()
        self.speed_combo.setAccessibleName("Modeled-Time presentation speed")
        for text, speed in zip(("0.25×", "0.5×", "1×", "2×", "4×", "8×"), SUPPORTED_SPEEDS):
            self.speed_combo.addItem(text, speed)
        self.speed_combo.setCurrentIndex(2)
        self.speed_combo.setEnabled(False)
        self.speed_combo.setToolTip("Presentation speed only; recorded modeled time is unchanged.")
        self.speed_combo.currentIndexChanged.connect(self._on_speed_changed)
        interval.addWidget(self.speed_combo)
        interval.addStretch()
        layout.addLayout(interval)
        self.playback_label = QLabel()
        layout.addWidget(self.playback_label)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self._update_playback_label()

        layout.addWidget(QLabel("Last applied action (committed trace)"))
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
                    min(self.board_container.height() + 450, available.height()))

    def _is_modeled_mode(self):
        return self.mode_combo.currentText() == "Modeled-Time"

    def _update_playback_label(self):
        rate = (f"Modeled-Time · {self.speed_combo.currentText()}" if self._is_modeled_mode()
                else f"Index · {self.interval_spin.value()} ms/step")
        self.playback_label.setText(f"Playback: {rate} (presentation)")

    def _on_interval_changed(self):
        if not self._is_modeled_mode():
            self.timer.setInterval(self.interval_spin.value())
        self._update_playback_label()

    def _on_mode_changed(self):
        if self._closed:
            return
        self._cancel_partial()
        modeled = self._is_modeled_mode()
        self.interval_spin.setEnabled(not modeled)
        self.speed_combo.setEnabled(modeled)
        self.timer.setTimerType(Qt.PreciseTimer if modeled else Qt.CoarseTimer)
        self.timer.setInterval(
            STAGE3_MODELED_FRAME_INTERVAL_MS if modeled else self.interval_spin.value(),
        )
        self._update_playback_label()

    def _on_speed_changed(self):
        if self._closed:
            return
        speed = self.speed_combo.currentData()
        if self._is_modeled_mode():
            self._run_modeled_operation(lambda: self.modeled_playback.set_speed(speed))
        else:
            self.modeled_playback.set_speed(speed)
        # A failed clock/action can prevent the requested rate from taking effect.
        blocked = self.speed_combo.blockSignals(True)
        try:
            self.speed_combo.setCurrentIndex(SUPPORTED_SPEEDS.index(self.modeled_playback.speed))
        finally:
            self.speed_combo.blockSignals(blocked)
        self._update_playback_label()

    def _update_presentation(self):
        playback = self.modeled_playback
        if (self._is_modeled_mode() and playback.pending_trace is not None
                and (playback.running or playback.partial_modeled_us > 0)):
            self.overlay.set_pending(playback.pending_trace, self.player.current_cursor, playback.progress)
            legend = MODELED_MOVEMENT_LEGEND
        else:
            self.overlay.set_trace(self.player.current_trace, self.player.current_cursor)
            legend = MOVEMENT_LEGEND
        if self.legend_label.text() != legend:
            self.legend_label.setText(legend)

    def _run_modeled_operation(self, operation):
        """Sample the controller once; render once after any boundary catch-up."""
        if self._closed:
            return
        before = self.player.current_index
        error = None
        try:
            operation()
        except Exception as exc:
            error = exc
        if self.player.current_index != before:
            self.refresh()
        else:
            self._update_presentation()
        if error is not None:
            self._stop_autoplay()
            self.error_label.setText(f"Playback stopped: {error}")
            self.error_label.show()
        else:
            self.error_label.hide()
            if self.modeled_playback.running:
                if not self.timer.isActive():
                    self.timer.start()
                self._set_play_button(True)
            else:
                self._stop_autoplay()

    def refresh(self):
        player = self.player
        for y, row in enumerate(player.get_observation()):
            for x, value in enumerate(row):
                self.cells[(x, y)].render_state(value)
        trace = player.current_trace
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
        self._update_presentation()

    def _cancel_partial(self):
        self._stop_autoplay()
        self.modeled_playback.cancel_partial()
        self.error_label.hide()
        self._update_presentation()

    def _set_play_button(self, running):
        text = "Pause" if running else "Play"
        if self.play_button.text() != text:
            self.play_button.setText(text)
            icon = QStyle.SP_MediaPause if running else QStyle.SP_MediaPlay
            self.play_button.setIcon(self.style().standardIcon(icon))

    def _stop_autoplay(self):
        self.timer.stop()
        self._set_play_button(False)

    def on_first(self):
        self._cancel_partial()
        self.player.go_to(0)
        self.refresh()

    def on_previous(self):
        self._cancel_partial()
        self.player.previous()
        self.refresh()

    def on_next(self):
        self._cancel_partial()
        self.player.next()
        self.refresh()

    def on_last(self):
        self._cancel_partial()
        self.player.go_to(self.player.step_count)
        self.refresh()

    def on_slider_changed(self, index: int):
        self._cancel_partial()
        self.player.go_to(index)
        self.refresh()

    def on_play_pause(self):
        if self._closed:
            return
        if self._is_modeled_mode():
            playback = self.modeled_playback
            self._run_modeled_operation(playback.pause if playback.running else playback.play)
        elif self.timer.isActive():
            self._stop_autoplay()
        elif not self._closed and self.player.current_index < self.player.step_count:
            self.timer.start()
            self._set_play_button(True)

    def _advance_autoplay(self):
        if self._closed or not self.timer.isActive():
            return
        if self._is_modeled_mode():
            self._run_modeled_operation(self.modeled_playback.update)
        else:
            self.player.next()
            self.refresh()

    def closeEvent(self, event):
        super().closeEvent(event)
        if event.isAccepted():
            self._stop_autoplay()
            self.modeled_playback.cancel_partial()
            if not self._closed:
                self._closed = True
                self.closed.emit()
