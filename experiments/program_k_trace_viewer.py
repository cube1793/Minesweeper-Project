"""D2/D3: public frames and logical knowledge from admitted completed D1 traces.

No evidence loading, gameplay reconstruction, inference, or answer lookup lives
here. Navigation selects immutable D1 frames. D3 marks only their hidden logical
mines; no pending-action knowledge, answer reference, or acquisition/proof panel
is consulted. Production code must not import this research module.
"""

from fractions import Fraction
from time import monotonic_ns

from PyQt5.QtCore import QPointF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSlider, QSpinBox, QStyle, QStyleOptionSlider, QVBoxLayout, QWidget,
)

from experiments.program_k_trace_adapter import (
    EXPLODED, FALSE_FLAG, FLAGGED, HIDDEN, MINE,
    KActionView, KTraceFrame, KTracePresentation,
)
from stage3_modeled_playback import SUPPORTED_SPEEDS, Stage3ModeledPlayback
from visualization_reference_overlays import NUMBER_COLORS, paint_action_target_route


CELL_SIZE = 28
INDEX_MODE = "Index"
MODEL_C_MODE = "Model C Time"
TICK_MS = 16
INDEX_INTERVAL_MIN_MS, INDEX_INTERVAL_MAX_MS, INDEX_INTERVAL_DEFAULT_MS = 20, 5000, 200
TITLE = "Program K Research Trace Viewer"
LIMITATION = (
    "Preserved accepted E1 K-P0 execution. Not statistically representative; "
    "not E2 effectiveness evidence; not production / Gate-P qualification."
)
CURSOR_NOTE = (
    "Blue ring: synthetic cursor. Orange outline: pending target during motion, otherwise last completed target. "
    "Muted route: completed action targets only. Straight paths and smoothstep are presentation, "
    "not recorded mouse movement."
)
TIME_NOTE = (
    "Model C is modeled physical execution time, not wall clock, compute time, or recorded human time. "
    "Board, action context, route and cumulative Model C time commit only at completed inputs."
)
KNOWLEDGE_COLOR = "#17663f"
KNOWLEDGE_DIAMOND_RADIUS = 6
KNOWLEDGE_NOTE = (
    "Green hollow diamond: K logical known mine, still physically HIDDEN. "
    "Red flag: physical FLAG. Tooltips distinguish explicit inputs and automatic WIN flags."
)


def _admitted(presentation):
    # D1 owns evidence authentication and semantic validation. This is only a
    # domain-type boundary; never parse/requalify its evidence in the viewer.
    if (type(presentation) is not KTracePresentation
            or type(presentation.actions) is not tuple or type(presentation.frames) is not tuple
            or not presentation.frames
            or not all(type(a) is KActionView for a in presentation.actions)
            or not all(type(f) is KTraceFrame for f in presentation.frames)):
        raise TypeError("Expected an admitted immutable D1 KTracePresentation.")
    return presentation


class KTracePlayer:
    """Integer frame navigation over D1; no Engine and no synthetic actions."""

    def __init__(self, presentation: KTracePresentation):
        self._presentation = _admitted(presentation)
        self._current_index = 0

    @property
    def presentation(self):
        return self._presentation

    @property
    def current_index(self):
        return self._current_index

    @property
    def step_count(self):
        return len(self.presentation.actions)

    @property
    def current_frame(self):
        return self.presentation.frame(self.current_index)

    @property
    def current_action(self):
        return self.presentation.actions[self.current_index - 1] if self.current_index else None

    @property
    def pending_action(self):
        return self.presentation.actions[self.current_index] if self.current_index < self.step_count else None

    @property
    def completed_route(self):
        return self.presentation.completed_route(self.current_index)

    def go_to(self, index: int):
        frame = self.presentation.frame(index)  # D1 rejects bool, negative, fractional and out-of-range indices.
        self._current_index = index
        return frame

    def next(self):
        if self.current_index == self.step_count:
            return False
        self.go_to(self.current_index + 1)
        return True

    def previous(self):
        if self.current_index == 0:
            return False
        self.go_to(self.current_index - 1)
        return True


class KTracePlayback(Stage3ModeledPlayback):
    """Narrow D1 bridge to the accepted exact Stage-3 clock/boundary controller.

    No fake Stage3Execution/Stage3RunResult. The base controller needs only
    current_index, step_count, next(), and the two pending-interval properties.
    In Index mode its interval units are PRESENTATION microseconds, never Model
    C state. Committed Model C values always come directly from D1 frames.
    """

    def __init__(self, player: KTracePlayer, *, clock=monotonic_ns):
        super().__init__(player, clock=clock)
        self._mode = INDEX_MODE
        self._index_interval_ms = INDEX_INTERVAL_DEFAULT_MS

    @property
    def mode(self):
        return self._mode

    @property
    def index_interval_ms(self):
        return self._index_interval_ms

    @property
    def pending_trace(self):
        return self._player.pending_action

    @property
    def pending_duration_us(self):
        if self.pending_trace is None:
            return None
        if self.mode == INDEX_MODE:
            return self.index_interval_ms * 1000
        return super().pending_duration_us  # D1's exact recorded modeled_action_us.

    @property
    def speed(self):
        return Fraction(1) if self.mode == INDEX_MODE else super().speed

    @property
    def model_speed(self):
        return super().speed

    def set_mode(self, mode):
        if mode not in (INDEX_MODE, MODEL_C_MODE):
            raise ValueError("Unknown presentation timing mode.")
        if mode != self.mode:
            self.cancel_partial()  # Align to the committed frame, without sampling/early commits.
            self._mode = mode

    def set_index_interval(self, milliseconds):
        if type(milliseconds) is not int or not INDEX_INTERVAL_MIN_MS <= milliseconds <= INDEX_INTERVAL_MAX_MS:
            raise ValueError("Index interval must be an integer in 20..5000 ms.")
        if self.mode == INDEX_MODE:
            self.update()  # Consume elapsed time at the OLD interval.
            progress = self.progress
            self._index_interval_ms = milliseconds
            # As in the accepted Exemplar Viewer, preserve normalized Index
            # progress when changing the interval, including while paused.
            self._partial_modeled_us = progress * (self.pending_duration_us or 0)
        else:
            self._index_interval_ms = milliseconds


class KPublicCell(QLabel):
    """Same public glyph convention as Stage-3; no click-to-gameplay signals."""

    def __init__(self, x, y, parent=None):
        super().__init__(parent)
        self.coordinate = (x, y)
        self.setFixedSize(CELL_SIZE, CELL_SIZE)
        self.setAlignment(Qt.AlignCenter)
        self.setFont(QFont("Arial", 14, QFont.Bold))

    def render_state(self, value):
        self.public_state = value
        background, color, border = "#c0c0c0", "#000000", "2px outset #ffffff"
        if value == HIDDEN:
            text, description = "", "HIDDEN"
        elif value == FLAGGED:
            text, description, color = "⚑", "physical FLAG (FLAGGED)", "#c00000"
        elif value == EXPLODED:
            text, description, background, border = "✹", "EXPLODED", "#ff5555", "1px solid #a0a0a0"
        elif value == MINE:
            text, description, border = "✹", "MINE", "1px solid #a0a0a0"
        elif value == FALSE_FLAG:
            text, description, color = "×", "FALSE_FLAG", "#c00000"
            background, border = "#e0e0e0", "1px solid #a0a0a0"
        elif 0 <= value <= 8:
            text, description = "" if value == 0 else str(value), f"Revealed {value}"
            color, background, border = NUMBER_COLORS.get(value, "#000000"), "#e0e0e0", "1px solid #a0a0a0"
        else:
            raise ValueError(f"Unsupported public cell state: {value}")
        self.setText(text)
        self.public_description = f"{self.coordinate}: {description}"
        self.setToolTip(self.public_description)
        self.setAccessibleName(self.toolTip())
        self.setStyleSheet(f"QLabel {{ background: {background}; color: {color}; border: {border};"
                          " margin: 0px; padding: 0px; }")

    def describe_knowledge(self, *, logical, explicit, automatic):
        """Secondary committed-frame facts; never change public text/style/state."""
        facts = [self.public_description]
        if explicit:
            facts.append("explicit physical FLAG (executed K input)")
        if automatic:
            facts.append("automatic WIN flag")
        if logical:
            facts.append("K logical known mine")
            if self.public_state == HIDDEN:
                facts.append("still physically HIDDEN")
        if self.public_state in (MINE, EXPLODED):
            facts.append("terminal public disclosure")
        self.setToolTip("; ".join(facts))
        self.setAccessibleName(self.toolTip())


class _KnowledgeOverlay(QWidget):
    """Optional marker layer sourced only from the committed D1 hidden-M set."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.NoFocus)
        self.hidden_mines = frozenset()

    def set_hidden_mines(self, cells):
        self.hidden_mines = cells
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(Qt.NoBrush)
        radius = KNOWLEDGE_DIAMOND_RADIUS
        for x, y in self.hidden_mines:
            cx, cy = (x + 0.5) * CELL_SIZE, (y + 0.5) * CELL_SIZE
            diamond = QPolygonF([QPointF(cx, cy - radius), QPointF(cx + radius, cy),
                                 QPointF(cx, cy + radius), QPointF(cx - radius, cy)])
            painter.setPen(QPen(QColor("#ffffff"), 4))
            painter.drawPolygon(diamond)
            painter.setPen(QPen(QColor(KNOWLEDGE_COLOR), 2))
            painter.drawPolygon(diamond)


class _MotionOverlay(QWidget):
    """Above public/knowledge layers: completed route < target < synthetic cursor."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.NoFocus)
        self.targets = ()
        self.show_route = True
        self.current_cursor = (0, 0)
        self.movement_start = self.action_target = None
        self.cursor_center = QPointF()

    @staticmethod
    def cell_center(coordinate):
        return QPointF((coordinate[0] + 0.5) * CELL_SIZE, (coordinate[1] + 0.5) * CELL_SIZE)

    @classmethod
    def interpolated_center(cls, start, target, progress):
        # Accepted Stage-3/Exemplar geometry. Float only at the rendering edge.
        u = max(0.0, min(1.0, float(progress)))
        eased = u * u * (3 - 2 * u)
        a, b = cls.cell_center(start), cls.cell_center(target)
        return a + (b - a) * eased

    def present(self, cursor, action, progress=None):
        self.current_cursor = cursor
        self.movement_start = action.cursor_before if action else None
        self.action_target = action.target if action else None
        self.cursor_center = (self.interpolated_center(action.cursor_before, action.target, progress)
                              if action is not None and progress is not None else self.cell_center(cursor))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.show_route:
            paint_action_target_route(painter, [self.cell_center(c) for c in self.targets])
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(Qt.NoBrush)
        if self.movement_start is not None and self.movement_start != self.action_target:
            start, end = map(self.cell_center, (self.movement_start, self.action_target))
            painter.setPen(QPen(QColor("#ffffff"), 4))
            painter.drawLine(start, end)
            painter.setPen(QPen(QColor("#2463c5"), 2))
            painter.drawLine(start, end)
        if self.action_target is not None:
            x, y = self.action_target
            painter.setPen(QPen(QColor("#cc7000"), 2))
            painter.drawRect(x * CELL_SIZE + 2, y * CELL_SIZE + 2, CELL_SIZE - 4, CELL_SIZE - 4)
        painter.setPen(QPen(QColor("#ffffff"), 4))
        painter.drawEllipse(self.cursor_center, 9, 9)
        painter.setPen(QPen(QColor("#2463c5"), 2))
        painter.drawEllipse(self.cursor_center, 9, 9)


class _PublicBoard(QWidget):
    def __init__(self, width, height):
        super().__init__()
        grid = QGridLayout(self)
        grid.setSpacing(0)
        grid.setContentsMargins(0, 0, 0, 0)
        self.cells = {}
        for y in range(height):
            for x in range(width):
                cell = KPublicCell(x, y, self)
                self.cells[x, y] = cell
                grid.addWidget(cell, y, x)
        self.setFixedSize(width * CELL_SIZE, height * CELL_SIZE)
        self.knowledge_overlay = _KnowledgeOverlay(self)
        self.knowledge_overlay.setGeometry(self.rect())
        self.overlay = _MotionOverlay(self)
        self.overlay.setGeometry(self.rect())
        self.overlay.raise_()

    def render(self, observation):
        self.observation = observation
        for y, row in enumerate(observation):
            for x, value in enumerate(row):
                self.cells[x, y].render_state(value)

    def render_knowledge(self, frame: KTraceFrame):
        self.knowledge_overlay.set_hidden_mines(frame.hidden_logical_mines)
        for coordinate, cell in self.cells.items():
            cell.describe_knowledge(logical=coordinate in frame.logical_mines,
                                    explicit=coordinate in frame.explicit_flags,
                                    automatic=coordinate in frame.automatic_flags)

    def show_knowledge(self, visible):
        self.knowledge_overlay.setVisible(visible)
        self.knowledge_overlay.stackUnder(self.overlay)


class _FrameSlider(QSlider):
    """Accepted handle-aware direct track seek without importing the V1 UI."""

    trackPressed = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            option = QStyleOptionSlider()
            self.initStyleOption(option)
            handle = self.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, self)
            if not handle.contains(event.pos()):
                span = max(1, self.width() - handle.width())
                position = max(0, min(span, event.x() - handle.width() // 2))
                self.trackPressed.emit()
                self.setValue(QStyle.sliderValueFromPosition(
                    self.minimum(), self.maximum(), position, span, option.upsideDown))
                event.accept()
                return
        super().mousePressEvent(event)


def _label(text=""):
    label = QLabel(text)
    label.setTextFormat(Qt.PlainText)
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return label


class KTraceViewerWindow(QWidget):
    """One owned Qt timer, in-memory D1 models, and no worker/job/process."""

    closed = pyqtSignal()

    def __init__(self, presentations: tuple[KTracePresentation, ...], parent=None, *, clock=monotonic_ns):
        if type(presentations) is not tuple or not presentations:
            raise TypeError("Supply a nonempty tuple of admitted D1 presentations.")
        self.presentations = tuple(_admitted(p) for p in presentations)
        super().__init__(parent, Qt.Window)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle(TITLE)
        self._clock, self._closed = clock, False
        self.player = self.playback = None
        self._rendered_frame = None
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.setInterval(TICK_MS)
        self.timer.timeout.connect(self._advance_playback)
        layout = QVBoxLayout(self)
        self.title_label = _label(TITLE)
        self.title_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(self.title_label)
        self.case_selector = QComboBox()
        self.case_selector.setAccessibleName("Preserved K-P0 case")
        for p in self.presentations:
            c = p.case
            self.case_selector.addItem(
                f"{c.case_id} · {p.terminal_status} · {c.width}×{c.height} / {c.num_mines} mines · "
                f"{len(p.actions)} inputs", c.schedule_index)
        layout.addWidget(self.case_selector)
        self.identity_label = _label()
        layout.addWidget(self.identity_label)
        self.status_label = _label()
        layout.addWidget(self.status_label)
        self.knowledge_label = _label()
        self.knowledge_label.setToolTip("Facts from the committed D1 frame; counts remain available with markers hidden.")
        layout.addWidget(self.knowledge_label)
        self.error_label = _label()
        self.error_label.setStyleSheet("color: #c00000;")
        self.error_label.hide()
        layout.addWidget(self.error_label)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(self.scroll_area, 1)
        self.legend_label = _label(KNOWLEDGE_NOTE + " " + CURSOR_NOTE)
        layout.addWidget(self.legend_label)
        controls = QHBoxLayout()
        for name, caption, icon, handler in (
            ("first_button", "First", QStyle.SP_MediaSkipBackward, self.on_first),
            ("previous_button", "Previous", QStyle.SP_MediaSeekBackward, self.on_previous),
            ("play_button", "Play", QStyle.SP_MediaPlay, self.on_play_pause),
            ("next_button", "Next", QStyle.SP_MediaSeekForward, self.on_next),
            ("last_button", "Last", QStyle.SP_MediaSkipForward, self.on_last),
        ):
            button = QPushButton(caption)
            button.setIcon(self.style().standardIcon(icon))
            button.clicked.connect(handler)
            setattr(self, name, button)
            controls.addWidget(button)
        self.route_checkbox = QCheckBox("Show completed route")
        self.route_checkbox.setChecked(True)
        self.route_checkbox.toggled.connect(self._route_changed)
        controls.addWidget(self.route_checkbox)
        self.knowledge_checkbox = QCheckBox("Show K logical known mines")
        self.knowledge_checkbox.setChecked(True)
        self.knowledge_checkbox.setToolTip(
            "Show markers on public HIDDEN cells only. Tooltips and counts retain committed K knowledge. "
            "Presentation only; no navigation or playback change.")
        self.knowledge_checkbox.toggled.connect(self._knowledge_changed)
        controls.addWidget(self.knowledge_checkbox)
        controls.addStretch()
        layout.addLayout(controls)
        position = QHBoxLayout()
        self.slider = _FrameSlider(Qt.Horizontal)
        self.slider.setAccessibleName("Completed K input count")
        self.slider.valueChanged.connect(self.seek)
        self.slider.sliderPressed.connect(self._cancel_partial)
        self.slider.trackPressed.connect(self._cancel_partial)
        position.addWidget(self.slider, 1)
        self.step_label = _label()
        position.addWidget(self.step_label)
        layout.addLayout(position)
        timing = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems((INDEX_MODE, MODEL_C_MODE))
        self.mode_combo.setAccessibleName("Playback timing mode")
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(INDEX_INTERVAL_MIN_MS, INDEX_INTERVAL_MAX_MS)
        self.interval_spin.setValue(INDEX_INTERVAL_DEFAULT_MS)
        self.interval_spin.setSuffix(" ms/input")
        self.interval_spin.setKeyboardTracking(False)
        self.interval_spin.setAccessibleName("Index presentation interval")
        self.interval_spin.setToolTip("Presentation interval only; exact recorded Model C costs stay unchanged.")
        self.speed_combo = QComboBox()
        for text, speed in zip(("0.25×", "0.5×", "1×", "2×", "4×", "8×"), SUPPORTED_SPEEDS):
            self.speed_combo.addItem(text, speed)
        self.speed_combo.setCurrentIndex(2)
        self.speed_combo.setAccessibleName("Model C Time playback speed")
        for caption, widget in (("Timing", self.mode_combo), ("Index interval", self.interval_spin),
                                ("Model C speed", self.speed_combo)):
            timing.addWidget(QLabel(caption + ":"))
            timing.addWidget(widget)
        timing.addStretch()
        layout.addLayout(timing)
        self.playback_label = _label()
        self.playback_label.setToolTip(TIME_NOTE)
        layout.addWidget(self.playback_label)
        layout.addWidget(_label("Last completed physical input (frame n−1 → n); coordinates are zero-based."))
        details = QGridLayout()
        self.detail_labels = {}
        for index, (key, caption) in enumerate((
            ("ordinal", "Action ordinal"), ("action", "Action"), ("target", "Target (x, y)"),
            ("cursor_before", "Cursor before"), ("modeled_action_us", "Action Model C cost"),
            ("cumulative_modeled_us", "Cumulative Model C time"), ("status_after", "Resulting status"),
            ("category", "K action category"), ("total_modeled_us", "Final trace Model C time"),
        )):
            row, col = divmod(index, 2)
            details.addWidget(QLabel(caption + ":"), row, col * 2)
            label = _label()
            self.detail_labels[key] = label
            details.addWidget(label, row, col * 2 + 1)
        layout.addLayout(details)
        self.limitation_label = _label(LIMITATION)
        layout.addWidget(self.limitation_label)
        self.case_selector.currentIndexChanged.connect(self.select_case)
        self.mode_combo.currentTextChanged.connect(self._mode_changed)
        self.interval_spin.valueChanged.connect(self._interval_changed)
        self.speed_combo.currentIndexChanged.connect(self._speed_changed)
        self.select_case(0)
        available = self.screen().availableGeometry()
        self.resize(min(1000, available.width()), min(900, available.height()))

    def select_case(self, index):
        if self._closed:
            return
        if type(index) is not int or not 0 <= index < len(self.presentations):
            raise ValueError("Invalid admitted case index.")
        self._cancel_partial()
        p = self.presentations[index]
        self.player = KTracePlayer(p)
        self.playback = KTracePlayback(self.player, clock=self._clock)
        self.playback.set_index_interval(self.interval_spin.value())
        self.playback.set_mode(self.mode_combo.currentText())
        self.playback.set_speed(self.speed_combo.currentData())
        self._rendered_frame = None
        old_board = self.scroll_area.takeWidget()
        if old_board is not None:
            old_board.deleteLater()
        self.board = _PublicBoard(p.case.width, p.case.height)
        self.scroll_area.setWidget(self.board)
        blocker = self.case_selector.blockSignals(True)
        self.case_selector.setCurrentIndex(index)
        self.case_selector.blockSignals(blocker)
        self.identity_label.setText(
            f"Accepted E1 K-P0 · {p.provenance.run_id} · schedule {p.case.schedule_index} · "
            f"repetition {p.case.repetition}")
        self.identity_label.setToolTip(
            f"Historical evidence SHA-256: {p.provenance.qualification_sha256}\n"
            f"Historical execution source: {p.provenance.execution_source_digest}\n"
            f"Board fingerprint: {p.case.board_fingerprint}\n"
            f"Model C profile: {p.provenance.profile_sha256}")
        self.refresh()

    def seek(self, index):
        if self._closed:
            return
        self.player.presentation.frame(index)  # Reject invalid navigation before disturbing playback.
        self._cancel_partial()
        self.player.go_to(index)
        self.refresh()

    def on_first(self):
        self.seek(0)

    def on_previous(self):
        self.seek(max(0, self.player.current_index - 1))

    def on_next(self):
        self.seek(min(self.player.step_count, self.player.current_index + 1))

    def on_last(self):
        self.seek(self.player.step_count)

    def _cancel_partial(self):
        self.timer.stop()
        if self.playback is not None:
            self.playback.cancel_partial()
            self.refresh()
        self.error_label.hide()

    def on_play_pause(self):
        if not self._closed:
            self._playback_operation(self.playback.pause if self.playback.running else self.playback.play)

    def _advance_playback(self):
        if not self._closed and self.timer.isActive():
            self._playback_operation(self.playback.update)

    def _playback_operation(self, operation):
        if self._closed:
            return
        try:
            operation()
        except Exception as exc:
            # Stage3ModeledPlayback stops on a clock/boundary failure and keeps
            # the last sampled position. Do not silently reset or advance it.
            self.timer.stop()
            self.error_label.setText(f"Playback stopped: {exc}")
            self.error_label.show()
        else:
            self.error_label.hide()
        self.refresh()

    def _mode_changed(self, mode):
        self._playback_operation(lambda: self.playback.set_mode(mode))

    def _interval_changed(self, interval):
        self._playback_operation(lambda: self.playback.set_index_interval(interval))

    def _speed_changed(self, _index):
        self._playback_operation(lambda: self.playback.set_speed(self.speed_combo.currentData()))

    def _route_changed(self, _checked):
        if not self._closed and self.player is not None:
            self.refresh()

    def _knowledge_changed(self, checked):
        # Do not sample/update the clock, navigate, refresh motion, or change
        # the route. Even unsampled elapsed time must stay untouched here.
        if not self._closed and self.player is not None:
            self.board.show_knowledge(checked)

    def refresh(self):
        if self._closed or self.player is None:
            return
        player, playback = self.player, self.playback
        frame, action = player.current_frame, player.current_action
        index, count = player.current_index, player.step_count
        if self._rendered_frame is not frame:
            self.board.render(frame.observation)
            self.board.render_knowledge(frame)
            self.board.show_knowledge(self.knowledge_checkbox.isChecked())
            self.knowledge_label.setText(
                f"K logical known mines: {len(frame.logical_mines)} · "
                f"Hidden logical known mines: {len(frame.hidden_logical_mines)} · "
                f"Explicit physical flags: {len(frame.explicit_flags)} · "
                f"Automatic WIN flags: {len(frame.automatic_flags)}")
            self.board.overlay.targets = player.completed_route
            self.step_label.setText(f"Frame {index} / {count}")
            self.status_label.setText(f"Public state: {frame.status} · {index} completed physical inputs")
            values = {"cumulative_modeled_us": f"{frame.cumulative_modeled_us:,} µs",
                      "total_modeled_us": f"{player.presentation.total_modeled_us:,} µs"}
            if action is not None:
                values.update(ordinal=f"{action.input_index + 1} / {count}", action=action.action,
                              target=str(action.target), cursor_before=str(action.cursor_before),
                              modeled_action_us=f"{action.modeled_action_us:,} µs",
                              status_after=action.status_after, category=action.category)
            for key, label in self.detail_labels.items():
                label.setText(values.get(key, "—"))
            blocker = self.slider.blockSignals(True)
            self.slider.setRange(0, count)
            self.slider.setValue(index)
            self.slider.blockSignals(blocker)
            self._rendered_frame = frame
        pending_motion = playback.pending_trace is not None and (playback.running or playback.progress > 0)
        self.board.overlay.show_route = self.route_checkbox.isChecked()
        self.board.overlay.present(frame.cursor, playback.pending_trace if pending_motion else action,
                                   playback.progress if pending_motion else None)
        self.first_button.setEnabled(index > 0)
        self.previous_button.setEnabled(index > 0)
        self.next_button.setEnabled(index < count)
        self.last_button.setEnabled(index < count)
        self.play_button.setEnabled(index < count)
        self.play_button.setText("Pause" if playback.running else "Play")
        icon = QStyle.SP_MediaPause if playback.running else QStyle.SP_MediaPlay
        self.play_button.setIcon(self.style().standardIcon(icon))
        if playback.running:
            if not self.timer.isActive():
                self.timer.start()
        else:
            self.timer.stop()
        modeled = playback.mode == MODEL_C_MODE
        self.interval_spin.setEnabled(not modeled)
        self.speed_combo.setEnabled(modeled)
        # Reflect accepted controller settings if a clock failure prevented a change.
        for widget, setter, value in (
            (self.mode_combo, self.mode_combo.setCurrentText, playback.mode),
            (self.interval_spin, self.interval_spin.setValue, playback.index_interval_ms),
            (self.speed_combo, self.speed_combo.setCurrentIndex, SUPPORTED_SPEEDS.index(playback.model_speed)),
        ):
            blocker = widget.blockSignals(True)
            setter(value)
            widget.blockSignals(blocker)
        rate = (f"Model C Time · {self.speed_combo.currentText()}" if modeled
                else f"Index · {playback.index_interval_ms} ms/input")
        self.playback_label.setText(f"Playback: {rate} (presentation only)")

    def closeEvent(self, event):
        super().closeEvent(event)
        if event.isAccepted() and not self._closed:
            self.timer.stop()
            self.playback.cancel_partial()
            self._closed = True
            self.closed.emit()
