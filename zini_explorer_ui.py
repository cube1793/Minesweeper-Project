"""Qt presentation of an already built ZiNi trace, by click playback unit.

The main UI owns eligibility, lazy trace construction, and session lifetime.
This window only reads the controller's playback API and delegates navigation
to it: one position per physical click (each flag, then the chord, of a
flag_chord move). Closing the window leaves the cached trace and the
controller's playback position intact.
"""

from PyQt5.QtCore import Qt, QTimer, QSize, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QCheckBox, QGraphicsOpacityEffect, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSlider,
    QSpinBox, QStyle, QStyleOptionSlider, QToolButton, QVBoxLayout, QWidget,
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
# Keyed by ZiniPlaybackUnitKind values (a str Enum), so no extra import here.
UNIT_KIND_TEXT = {
    "click": "클릭",
    "fallback_click": "fallback 클릭",
    "chord": "화음",
}
DEFAULT_INTERVAL_MS = 500
UNIT_NOTE_TEXT = (
    "깃발 순서는 좌상단(행 우선) 표시 순서이며 실제 클릭 순서가 아닙니다. "
    "Premium·선택 관계·동률 수 외의 값은 논리 단계 전체 기준입니다."
)


def unit_kind_text(unit) -> str:
    if unit.kind == "flag":
        return f"깃발 {unit.flag_number}/{unit.flag_count}"
    return UNIT_KIND_TEXT[unit.kind]


class ZiniExplorerCell(QLabel):
    """Read-only cell with independent base state and step overlays."""

    def __init__(self, x: int, y: int, parent=None):
        super().__init__(parent)
        self.setFixedSize(CELL_SIZE, CELL_SIZE)
        self.setAlignment(Qt.AlignCenter)
        self.setFont(QFont("Arial", 14, QFont.Bold))
        self.setToolTip(f"({x}, {y})")
        # Fade only the answer glyph (including color emoji), never the cover.
        self.answer_label = QLabel(self)
        self.answer_label.setFont(self.font())
        self.answer_label.setGeometry(self.rect())
        self.answer_label.setAlignment(Qt.AlignCenter)
        self.answer_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        opacity = QGraphicsOpacityEffect(self.answer_label)
        opacity.setOpacity(0.35)
        self.answer_label.setGraphicsEffect(opacity)
        self.render_state("closed")

    def render_state(self, state: str, value: int = 0, *, selected: bool = False,
                     newly_revealed: bool = False, newly_flagged: bool = False,
                     show_answer: bool = False, is_mine: bool = False):
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

        answer = ""
        if state == "closed" and show_answer:
            answer = "💣" if is_mine else str(value) if value else ""
        self.answer_label.setText(answer)
        answer_color = "#000000" if is_mine else NUMBER_COLORS.get(value, "#000000")
        self.answer_label.setStyleSheet(
            "QLabel { background-color: transparent; border: none;"
            f" color: {answer_color}; margin: 0px; padding: 0px; }}"
        )
        self.answer_label.setVisible(bool(answer))

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


class _JumpSlider(QSlider):
    """Horizontal, handle-aware track seeking; handle drags stay native Qt."""

    trackPressed = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            option = QStyleOptionSlider()
            self.initStyleOption(option)
            handle = self.style().subControlRect(
                QStyle.CC_Slider, option, QStyle.SC_SliderHandle, self,
            )
            if not handle.contains(event.pos()):
                # Use the handle's travel span, as the main Replay slider does.
                span = max(1, self.width() - handle.width())
                position = max(0, min(span, event.x() - handle.width() // 2))
                # Stop playback even when rounding maps to the current index.
                self.trackPressed.emit()
                self.setValue(QStyle.sliderValueFromPosition(
                    self.minimum(), self.maximum(), position, span, option.upsideDown,
                ))
                event.accept()
                return
        super().mousePressEvent(event)


class ZiniExplorerWindow(QWidget):
    """Separate click-unit view of one trace-ready controller session.

    Construction never requests a trace. Reopening a valid cached session
    preserves its playback position; only the autoplay timer belongs to this
    view. The window uses the controller's playback API, never its logical one.
    """

    closed = pyqtSignal()

    def __init__(self, controller: ZiniExplorerController, parent=None):
        if (controller.state != "ready" or controller.trace is None
                or controller.snapshot is None or controller.playback_position is None):
            raise ValueError("ZiNi Explorer requires an eligible, trace-ready controller.")
        super().__init__(parent, Qt.Window)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.controller = controller
        self._session_token = controller.token
        self.setWindowTitle("ZiNi Explorer")
        self._initial_size_applied = False
        self._details_auto_resize = None

        self.timer = QTimer(self)
        self.timer.setInterval(DEFAULT_INTERVAL_MS)
        self.timer.timeout.connect(self._advance_autoplay)
        layout = QVBoxLayout(self)

        counts = QHBoxLayout()
        self.clicks_label = QLabel()
        self.clicks_label.setFont(QFont("Arial", 12, QFont.Bold))
        counts.addWidget(self.clicks_label)
        counts.addStretch()
        self.answer_display_checkbox = QCheckBox("미공개 정답 표시")
        self.answer_display_checkbox.setChecked(True)
        self.answer_display_checkbox.toggled.connect(self._refresh_board)
        counts.addWidget(self.answer_display_checkbox)
        layout.addLayout(counts)

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
            ("새로 꽂은 깃발", "background-color: #ffe2a8;"),
        ):
            label = QLabel(text)
            label.setStyleSheet(f"QLabel {{ {style} padding: 3px; }}")
            legend.addWidget(label)
        legend.addStretch()
        layout.addLayout(legend)

        controls = QHBoxLayout()
        button_specs = (
            ("first_button", QStyle.SP_MediaSkipBackward, "처음", self.on_first),
            ("previous_button", QStyle.SP_MediaSeekBackward, "이전 재생 단위", self.on_previous),
            ("play_button", QStyle.SP_MediaPlay, "재생", self.on_play_pause),
            ("next_button", QStyle.SP_MediaSeekForward, "다음 재생 단위", self.on_next),
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
        controls.addWidget(QLabel("재생 간격"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(20, 5000)
        self.interval_spin.setValue(DEFAULT_INTERVAL_MS)
        self.interval_spin.setSuffix(" ms/클릭")
        self.interval_spin.setToolTip("재생 단위(클릭 1회)당 자동 재생 간격")
        self.interval_spin.valueChanged.connect(self.timer.setInterval)
        controls.addWidget(self.interval_spin)
        layout.addLayout(controls)

        self.slider = _JumpSlider(Qt.Horizontal)
        self.slider.setAccessibleName("재생 위치 (누적 Clicks)")
        self.slider.valueChanged.connect(self.on_slider_changed)
        self.slider.sliderPressed.connect(self._stop_autoplay)
        self.slider.trackPressed.connect(self._stop_autoplay)
        layout.addWidget(self.slider)

        self.details_button = QToolButton()
        self.details_button.setText("상세 정보")
        self.details_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.details_button.setArrowType(Qt.RightArrow)
        self.details_button.setCheckable(True)
        self.details_button.toggled.connect(self._toggle_details)
        layout.addWidget(self.details_button)
        self.details_panel = QWidget()
        details_layout = QVBoxLayout(self.details_panel)
        details_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.details_panel)
        self.details_panel.hide()
        self.unit_note_label = QLabel(UNIT_NOTE_TEXT)
        self.unit_note_label.setWordWrap(True)
        details_layout.addWidget(self.unit_note_label)
        # Two columns keep the expanded panel no taller than the former single
        # list: the click unit and whole-move values on the left, the move's
        # pre-state Premium diagnostics on the right.
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(18)
        details_layout.addLayout(grid)
        self.diagnostic_labels = {}
        self.diagnostic_rows = {}
        captions = {0: [], 1: []}
        for key, caption, row_index, column in (
            ("unit", "재생 단위 · 대상 좌표 · 논리 단계", 0, 0),
            ("action", "Action", 1, 0),
            ("coordinate", "논리 단계 좌표 (x, y; 0부터)", 2, 0),
            ("newly_revealed", "새로 열린 칸", 3, 0),
            ("newly_flagged", "새로 꽂은 깃발", 4, 0),
            ("premium_basis", "Premium 기준 시점", 0, 1),
            ("premium", "Move Premium", 1, 1),
            ("best_premium", "적용 전 최대 Premium", 2, 1),
            ("selection", "선택 관계 (적용 전 상태)", 3, 1),
            ("tie_count", "최대 Premium 숫자 칸 동률 수", 4, 1),
        ):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            caption_label = QLabel(caption)
            row_layout.addWidget(caption_label)
            value_label = QLabel("—")
            value_label.setWordWrap(True)
            row_layout.addWidget(value_label, 1)
            captions[column].append(caption_label)
            self.diagnostic_labels[key] = value_label
            self.diagnostic_rows[key] = row
            grid.addWidget(row, row_index, column)
        for column, labels in captions.items():
            # Align values within each column, as the former fixed width did.
            width = max(label.sizeHint().width() for label in labels)
            for label in labels:
                label.setMinimumWidth(width)
            grid.setColumnStretch(column, 1)
        self.refresh()

    def _toggle_details(self, expanded: bool):
        previous_size = self.size()
        self.details_panel.setVisible(expanded)
        self.details_button.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        if self.isVisible():
            self.layout().activate()
        if not expanded:
            sizes = self._details_auto_resize
            self._details_auto_resize = None
            if sizes is not None and previous_size == sizes[1]:
                # Restore only our own growth; keep any user resize and position.
                self.resize(sizes[0])
            return

        self._details_auto_resize = None
        if expanded and self.isVisible():
            scroll_frame = 2 * self.scroll_area.frameWidth()
            required_height = self.board_container.height() + scroll_frame
            # A board wider than the scroll area still needs its horizontal bar.
            # Ignore a temporary vertical bar: growing may remove both bars.
            if self.board_container.width() > self.scroll_area.width() - scroll_frame:
                required_height += self.scroll_area.horizontalScrollBar().sizeHint().height()
            extra_height = max(0, required_height - self.scroll_area.height())
            self._resize_within_available_screen(QSize(self.width(), self.height() + extra_height))
            if self.height() > previous_size.height():
                self._details_auto_resize = (previous_size, self.size())

    def showEvent(self, event):
        super().showEvent(event)
        if not self._initial_size_applied:
            self._initial_size_applied = True
            self._apply_initial_window_size()

    def _apply_initial_window_size(self):
        """Fit the board plus measured chrome, keeping scrolling for small screens."""
        self.layout().activate()
        margins = self.layout().contentsMargins()
        hint = self.layout().sizeHint()
        board = self.board_container.size()
        scroll_frame = 2 * self.scroll_area.frameWidth()
        chrome_height = hint.height() - self.scroll_area.sizeHint().height()
        desired = QSize(
            max(hint.width(), board.width() + scroll_frame + margins.left() + margins.right()),
            board.height() + scroll_frame + chrome_height,
        )
        self._resize_within_available_screen(desired)

    def _resize_within_available_screen(self, desired: QSize):
        # On first show the native frame is available, unlike construction time.
        available = self.screen().availableGeometry()
        frame_size = self.frameGeometry().size() - self.size()
        self.resize(desired.boundedTo(available.size() - frame_size))
        frame = self.frameGeometry()
        self.move(
            max(available.left(), min(frame.left(), available.right() - frame.width() + 1)),
            max(available.top(), min(frame.top(), available.bottom() - frame.height() + 1)),
        )

    def _session_ready(self) -> bool:
        return (
            self.controller.token == self._session_token
            and self.controller.state == "ready"
            and self.controller.trace is not None
            and self.controller.snapshot is not None
            and self.controller.playback_position is not None
        )

    def _refresh_board(self):
        """Rerender cells only; display changes never navigate or request a trace."""
        ready = self._session_ready()
        controller = self.controller
        snapshot = controller.snapshot if ready else None
        unit = controller.playback_unit if ready else None
        revealed = controller.playback_revealed if ready else frozenset()
        flagged = controller.playback_flagged_mines if ready else frozenset()
        newly_revealed = controller.playback_newly_revealed if ready else frozenset()
        newly_flagged = controller.playback_newly_flagged if ready else frozenset()
        # A flag unit selects its flag cell; chord/click/fallback the move cell.
        selected = unit.target if unit else None
        for coordinate, cell in self.cells.items():
            x, y = coordinate
            state = (
                "flagged" if coordinate in flagged else
                "revealed" if coordinate in revealed else "closed"
            )
            value = snapshot.adjacent[y][x] if snapshot is not None else 0
            cell.render_state(
                state, value, selected=coordinate == selected,
                newly_revealed=coordinate in newly_revealed,
                newly_flagged=coordinate in newly_flagged,
                show_answer=ready and self.answer_display_checkbox.isChecked(),
                is_mine=snapshot is not None and coordinate in snapshot.mines,
            )

    def refresh(self):
        """Render only the controller's exposed snapshot, state, and current unit."""
        self._refresh_board()
        ready = self._session_ready()
        unit = self.controller.playback_unit if ready else None
        step = self.controller.playback_step if ready else None
        position = self.controller.playback_position if ready else 0
        count = self.controller.playback_count if ready else 0
        if not ready or position == count:
            self._stop_autoplay()
        # One unit is one physical click, so the position is the click count.
        self.clicks_label.setText(
            f"Clicks {position} / {self.controller.clicks}"
            if ready else "Clicks — / —"
        )
        values = {}
        if unit is not None and step is not None:
            step_number = step.step_index + 1
            values = {
                "unit": (
                    f"{unit_kind_text(unit)} · ({unit.target[0]}, {unit.target[1]})"
                    f" · {step_number} / {len(self.controller.trace.steps)}"
                ),
                "premium_basis": f"논리 단계 {step_number}의 적용 전 상태 기준",
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
            self.slider.setValue(position)
            self.slider.setEnabled(ready and count > 0)
        finally:
            self.slider.blockSignals(previous_block)
        self.first_button.setEnabled(ready and position > 0)
        self.previous_button.setEnabled(ready and position > 0)
        self.next_button.setEnabled(ready and position < count)
        self.last_button.setEnabled(ready and position < count)
        self.play_button.setEnabled(ready and position < count)

    def _stop_autoplay(self):
        self.timer.stop()
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_button.setToolTip("재생")
        self.play_button.setAccessibleName("재생")

    def on_first(self):
        self._stop_autoplay()
        if self._session_ready():
            self.controller.seek_playback(0)
        self.refresh()

    def on_previous(self):
        self._stop_autoplay()
        if self._session_ready():
            self.controller.previous_playback()
        self.refresh()

    def on_next(self):
        self._stop_autoplay()
        if self._session_ready():
            self.controller.next_playback()
        self.refresh()

    def on_last(self):
        self._stop_autoplay()
        if self._session_ready():
            self.controller.seek_playback(self.controller.playback_count)
        self.refresh()

    def on_slider_changed(self, position: int):
        self._stop_autoplay()
        if self._session_ready():
            self.controller.seek_playback(position)
        self.refresh()

    def on_play_pause(self):
        if self.timer.isActive():
            self._stop_autoplay()
        elif (self._session_ready()
              and self.controller.playback_position < self.controller.playback_count):
            self.timer.start(self.interval_spin.value())
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
            self.play_button.setToolTip("일시 정지")
            self.play_button.setAccessibleName("일시 정지")

    def _advance_autoplay(self):
        if not self.timer.isActive():
            return
        if self._session_ready():
            self.controller.next_playback()
        self.refresh()

    def closeEvent(self, event):
        self._stop_autoplay()
        super().closeEvent(event)
        if event.isAccepted():
            self.closed.emit()
