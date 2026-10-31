"""D4.2: two independent presentations of an admitted completed E1 pair.

No evidence IO, gameplay, shared playhead, normalized progress, or answer lookup.
The only cross-panel operation is selecting another already-admitted pair.
"""

from time import monotonic_ns

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSizePolicy, QSpinBox, QStyle, QVBoxLayout, QWidget,
)

from experiments.program_k_control_trace_adapter import (
    ControlActionView, ControlTraceFrame, ControlTracePresentation,
)
from experiments.program_k_trace_comparison import ProgramKComparisonPair, LIMITATION
from experiments.program_k_trace_viewer import (
    CELL_SIZE, CURSOR_NOTE, INDEX_MODE, MODEL_C_MODE, SUPPORTED_SPEEDS, TICK_MS,
    INDEX_INTERVAL_MIN_MS, INDEX_INTERVAL_MAX_MS, INDEX_INTERVAL_DEFAULT_MS,
    KTracePlayer, KTracePlayback, KPublicCell, _PublicBoard, _MotionOverlay, _FrameSlider, _label,
)


TITLE = "Program K Research Comparison — CONTROL ↔ K-P0"
FIXED_PAIR_INDICES = ((6, 8), (12, 14), (18, 20), (24, 26))
LOSS_TIME_NOTE = (
    "Not applicable for speed-to-win interpretation; each side's termination cost is shown separately."
)


class ControlTracePlayer:
    """CONTROL-only physical navigation; never masquerades as a D1 K model."""

    def __init__(self, presentation):
        if (type(presentation) is not ControlTracePresentation
                or type(presentation.actions) is not tuple or type(presentation.frames) is not tuple
                or not presentation.frames
                or not all(type(a) is ControlActionView for a in presentation.actions)
                or not all(type(f) is ControlTraceFrame for f in presentation.frames)):
            raise TypeError("Expected an admitted immutable CONTROL presentation.")
        self.presentation = presentation
        self._current_index = 0

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

    def go_to(self, index):
        frame = self.presentation.frame(index)
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


class _ControlBoard(QWidget):
    """Public cells and physical provenance only; no K knowledge layer exists."""

    def __init__(self, width, height):
        super().__init__()
        grid = QGridLayout(self)
        grid.setSpacing(0)
        grid.setContentsMargins(0, 0, 0, 0)
        self.cells = {}
        for y in range(height):
            for x in range(width):
                cell = KPublicCell(x, y, self)  # render_state is strictly public glyph presentation.
                self.cells[x, y] = cell
                grid.addWidget(cell, y, x)
        self.setFixedSize(width * CELL_SIZE, height * CELL_SIZE)
        self.overlay = _MotionOverlay(self)
        self.overlay.setGeometry(self.rect())
        self.overlay.raise_()

    def render_frame(self, frame):
        self.observation = frame.observation
        for (x, y), cell in self.cells.items():
            cell.render_state(frame.observation[y][x])
            facts = [cell.public_description]
            if (x, y) in frame.explicit_flags:
                facts.append("explicit physical FLAG (executed CONTROL input)")
            if (x, y) in frame.automatic_flags:
                facts.append("automatic WIN flag; no executed FLAG input")
            if cell.public_state in (-4, -5):
                facts.append("terminal public disclosure")
            cell.setToolTip("; ".join(facts))
            cell.setAccessibleName(cell.toolTip())


class _TracePanel(QGroupBox):
    """Research-local physical panel; each instance owns its controller and timer."""

    def __init__(self, *, is_control, clock, parent=None):
        super().__init__("CONTROL — frozen Stage-3 V1 physical execution" if is_control else
                         "K-P0 — Program K physical execution", parent)
        self.is_control = is_control
        self.variant = "CONTROL" if is_control else "K-P0"
        self._clock, self._closed = clock, False
        self.player = self.playback = None
        self._rendered_frame = None
        self.setMinimumWidth(470)
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.setInterval(TICK_MS)
        self.timer.timeout.connect(self._advance_playback)
        layout = QVBoxLayout(self)
        self.summary_label = _label()
        self.summary_label.setMinimumHeight(48)
        layout.addWidget(self.summary_label)
        self.status_label = _label()
        layout.addWidget(self.status_label)
        self.state_label = _label()
        self.state_label.setMinimumHeight(36)
        layout.addWidget(self.state_label)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.scroll_area.setMinimumHeight(150)
        self.scroll_area.setAccessibleName(self.variant + " public board scroll area")
        layout.addWidget(self.scroll_area, 1)
        toggles = QHBoxLayout()
        self.route_checkbox = QCheckBox("Show completed route")
        self.route_checkbox.setChecked(True)
        self.route_checkbox.toggled.connect(self.refresh)
        toggles.addWidget(self.route_checkbox)
        self.knowledge_checkbox = None
        if not is_control:
            self.knowledge_checkbox = QCheckBox("Show K logical known mines")
            self.knowledge_checkbox.setChecked(True)
            self.knowledge_checkbox.toggled.connect(self._knowledge_changed)
            self.knowledge_checkbox.setToolTip("Green hollow diamonds: committed K knowledge on public HIDDEN cells only.")
            toggles.addWidget(self.knowledge_checkbox)
        toggles.addStretch()
        layout.addLayout(toggles)
        navigation = QHBoxLayout()
        for name, caption, icon, callback in (
            ("first_button", "First", QStyle.SP_MediaSkipBackward, self.on_first),
            ("previous_button", "Previous", QStyle.SP_MediaSeekBackward, self.on_previous),
            ("play_button", "Play", QStyle.SP_MediaPlay, self.on_play_pause),
            ("next_button", "Next", QStyle.SP_MediaSeekForward, self.on_next),
            ("last_button", "Last", QStyle.SP_MediaSkipForward, self.on_last),
        ):
            button = QPushButton(caption)
            button.setIcon(self.style().standardIcon(icon))
            button.setAccessibleName(self.variant + " " + caption)
            button.clicked.connect(callback)
            setattr(self, name, button)
            navigation.addWidget(button)
        layout.addLayout(navigation)
        self.slider = _FrameSlider(Qt.Horizontal)
        self.slider.setAccessibleName(self.variant + " completed physical input count")
        self.slider.valueChanged.connect(self.seek)
        self.slider.sliderPressed.connect(self.cancel_partial)
        self.slider.trackPressed.connect(self.cancel_partial)
        layout.addWidget(self.slider)
        timing = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems((INDEX_MODE, MODEL_C_MODE))
        self.mode_combo.setAccessibleName(self.variant + " timing mode")
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(INDEX_INTERVAL_MIN_MS, INDEX_INTERVAL_MAX_MS)
        self.interval_spin.setValue(INDEX_INTERVAL_DEFAULT_MS)
        self.interval_spin.setSuffix(" ms/input")
        self.interval_spin.setKeyboardTracking(False)
        self.interval_spin.setAccessibleName(self.variant + " Index interval")
        self.speed_combo = QComboBox()
        for text, speed in zip(("0.25×", "0.5×", "1×", "2×", "4×", "8×"), SUPPORTED_SPEEDS):
            self.speed_combo.addItem(text, speed)
        self.speed_combo.setCurrentIndex(2)
        self.speed_combo.setAccessibleName(self.variant + " Model C rate")
        for caption, widget in (("Timing", self.mode_combo), ("Index", self.interval_spin), ("Rate", self.speed_combo)):
            timing.addWidget(QLabel(caption))
            timing.addWidget(widget)
        layout.addLayout(timing)
        self.playback_label = _label()
        layout.addWidget(self.playback_label)
        layout.addWidget(_label("Last completed input · coordinates are zero-based"))
        details = QGridLayout()
        self.detail_labels = {}
        captions = [("ordinal", "Ordinal"), ("action", "Action"), ("target", "Target"),
                    ("cursor_before", "Cursor before"), ("modeled_action_us", "Action Model C"),
                    ("cumulative_modeled_us", "Cumulative Model C"), ("status_after", "Resulting status")]
        if not is_control:
            captions.append(("category", "K category"))
        for i, (key, caption) in enumerate(captions):
            row, col = divmod(i, 2)
            details.addWidget(QLabel(caption + ":"), row, col * 2)
            label = _label()
            label.setMinimumWidth(55)
            self.detail_labels[key] = label
            details.addWidget(label, row, col * 2 + 1)
        layout.addLayout(details)
        self.error_label = _label()
        self.error_label.setStyleSheet("color: #b00000;")
        self.error_label.hide()
        layout.addWidget(self.error_label)
        self.mode_combo.currentTextChanged.connect(lambda mode: self._operate(lambda: self.playback.set_mode(mode)))
        self.interval_spin.valueChanged.connect(lambda value: self._operate(lambda: self.playback.set_index_interval(value)))
        self.speed_combo.currentIndexChanged.connect(lambda _: self._operate(lambda: self.playback.set_speed(self.speed_combo.currentData())))

    def load_trace(self, presentation, facts):
        self.cancel_partial()
        self.player = ControlTracePlayer(presentation) if self.is_control else KTracePlayer(presentation)
        # KTracePlayback's accepted physical timing bridge reads pending_action,
        # modeled_action_us, step_count/current_index/next only. No K state/labels.
        self.playback = KTracePlayback(self.player, clock=self._clock)
        self.playback.set_index_interval(self.interval_spin.value())
        self.playback.set_mode(self.mode_combo.currentText())
        self.playback.set_speed(self.speed_combo.currentData())
        self._rendered_frame = None
        old_board = self.scroll_area.takeWidget()
        if old_board is not None:
            old_board.deleteLater()
        self.board = (_ControlBoard if self.is_control else _PublicBoard)(presentation.case.width, presentation.case.height)
        self.scroll_area.setWidget(self.board)
        self.summary_label.setText(
            f"Recorded completed trace: {facts.outcome} · Inputs {facts.total_inputs} · "
            f"OPEN {facts.open_inputs} · FLAG {facts.flag_inputs} · CHORD {facts.chord_inputs}\n"
            f"Final Model C: {facts.model_c_total_us:,} µs · Explicit flags {facts.explicit_physical_flags} · "
            f"Automatic WIN flags {facts.automatic_win_flags}")
        self.refresh()

    def seek(self, index):
        if self._closed:
            return
        self.player.presentation.frame(index)
        self.cancel_partial()
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

    def cancel_partial(self):
        self.timer.stop()
        if self.playback is not None:
            self.playback.cancel_partial()
            self.refresh()
        self.error_label.hide()

    def on_play_pause(self):
        if not self._closed:
            self._operate(self.playback.pause if self.playback.running else self.playback.play)

    def _advance_playback(self):
        if not self._closed and self.timer.isActive():
            self._operate(self.playback.update)

    def _operate(self, operation):
        if self._closed:
            return
        try:
            operation()
        except Exception as exc:
            self.timer.stop()
            self.error_label.setText(f"Playback stopped: {exc}")
            self.error_label.show()
        else:
            self.error_label.hide()
        self.refresh()

    def _knowledge_changed(self, checked):
        if not self._closed and self.player is not None:
            self.board.show_knowledge(checked)  # Does not sample either clock or refresh motion.

    def refresh(self, *_):
        if self._closed or self.player is None:
            return
        player, playback = self.player, self.playback
        frame, action = player.current_frame, player.current_action
        index, count = player.current_index, player.step_count
        if self._rendered_frame is not frame:
            if self.is_control:
                self.board.render_frame(frame)
                state = ""
            else:
                self.board.render(frame.observation)
                self.board.render_knowledge(frame)
                self.board.show_knowledge(self.knowledge_checkbox.isChecked())
                state = (f"K logical known mines: {len(frame.logical_mines)} · "
                         f"Hidden logical known mines: {len(frame.hidden_logical_mines)}\n")
            self.state_label.setText(state + f"Explicit physical flags: {len(frame.explicit_flags)} · "
                                     f"Automatic WIN flags: {len(frame.automatic_flags)}")
            self.board.overlay.targets = player.completed_route
            self.status_label.setText(f"Committed frame {index} / {count} · Public state: {frame.status}")
            values = {"cumulative_modeled_us": f"{frame.cumulative_modeled_us:,} µs"}
            if action is not None:
                values.update(ordinal=f"{action.input_index + 1} / {count}", action=action.action,
                              target=str(action.target), cursor_before=str(action.cursor_before),
                              modeled_action_us=f"{action.modeled_action_us:,} µs", status_after=action.status_after)
                if not self.is_control:
                    values["category"] = action.category
            for name, label in self.detail_labels.items():
                label.setText(values.get(name, "—"))
            blocked = self.slider.blockSignals(True)
            self.slider.setRange(0, count)
            self.slider.setValue(index)
            self.slider.blockSignals(blocked)
            self._rendered_frame = frame
        partial = playback.pending_trace is not None and (playback.running or playback.progress > 0)
        self.board.overlay.show_route = self.route_checkbox.isChecked()
        self.board.overlay.present(frame.cursor, playback.pending_trace if partial else action,
                                   playback.progress if partial else None)
        for button in (self.first_button, self.previous_button):
            button.setEnabled(index > 0)
        for button in (self.next_button, self.last_button, self.play_button):
            button.setEnabled(index < count)
        self.play_button.setText("Pause" if playback.running else "Play")
        self.play_button.setAccessibleName(self.variant + " " + self.play_button.text())
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause if playback.running else QStyle.SP_MediaPlay))
        if playback.running:
            if not self.timer.isActive():
                self.timer.start()
        else:
            self.timer.stop()
        modeled = playback.mode == MODEL_C_MODE
        self.interval_spin.setEnabled(not modeled)
        self.speed_combo.setEnabled(modeled)
        for widget, setter, value in (
            (self.mode_combo, self.mode_combo.setCurrentText, playback.mode),
            (self.interval_spin, self.interval_spin.setValue, playback.index_interval_ms),
            (self.speed_combo, self.speed_combo.setCurrentIndex, SUPPORTED_SPEEDS.index(playback.model_speed)),
        ):
            blocked = widget.blockSignals(True)
            setter(value)
            widget.blockSignals(blocked)
        rate = f"Model C Time · {self.speed_combo.currentText()}" if modeled else f"Index · {playback.index_interval_ms} ms/input"
        self.playback_label.setText(f"{'Playing' if playback.running else 'Paused'} · {rate} · presentation only")

    def shutdown(self):
        self.timer.stop()
        if self.playback is not None:
            self.playback.cancel_partial()
        self._closed = True


class ProgramKComparisonWindow(QWidget):
    """The pair selector owns identity only; both panels own their own clocks."""

    closed = pyqtSignal()

    def __init__(self, pairs, parent=None, *, control_clock=monotonic_ns, kp0_clock=monotonic_ns):
        if (type(pairs) is not tuple or not pairs or not all(type(p) is ProgramKComparisonPair for p in pairs)
                or len({p.control.case.schedule_index for p in pairs}) != len(pairs)
                or any((p.control.case.schedule_index, p.kp0.case.schedule_index) not in FIXED_PAIR_INDICES for p in pairs)):
            raise TypeError("Supply distinct admitted D4.1 ProgramKComparisonPair objects.")
        super().__init__(parent, Qt.Window)
        self.pairs = pairs
        self._closed = False
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle(TITLE)
        layout = QVBoxLayout(self)
        title = _label(TITLE)
        title.setFont(QFont("Arial", 13, QFont.Bold))
        layout.addWidget(title)
        self.pair_selector = QComboBox()
        self.pair_selector.setAccessibleName("Preserved same-board pair")
        for p in pairs:
            identity = p.identity
            self.pair_selector.addItem(f"{identity.case_id} · {identity.width}×{identity.height} / {identity.num_mines} mines · "
                                      f"CONTROL {identity.control_schedule_index} ↔ K-P0 {identity.kp0_schedule_index}", identity.case_id)
        layout.addWidget(self.pair_selector)
        self.identity_label, self.fingerprint_label = _label(), _label()
        self.fingerprint_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        layout.addWidget(self.identity_label)
        layout.addWidget(self.fingerprint_label)
        self.limitation_label = _label(LIMITATION + " Not production / Gate-P qualification.")
        layout.addWidget(self.limitation_label)
        self.difference_heading, self.difference_label, self.difference_note = _label(), _label(), _label()
        self.difference_heading.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(self.difference_heading)
        layout.addWidget(self.difference_label)
        layout.addWidget(self.difference_note)
        panels = QHBoxLayout()
        self.control_panel = _TracePanel(is_control=True, clock=control_clock, parent=self)
        self.kp0_panel = _TracePanel(is_control=False, clock=kp0_clock, parent=self)
        panels.addWidget(self.control_panel, 1)
        panels.addWidget(self.kp0_panel, 1)
        layout.addLayout(panels, 1)
        self.legend_label = _label("K-P0 only: green hollow diamond = K logical known mine still HIDDEN. Red flag = physical FLAG. " + CURSOR_NOTE)
        layout.addWidget(self.legend_label)
        time_note = _label("Model C is modeled physical execution time; not wall clock, compute time, or recorded human time. Each panel has its own sequence.")
        layout.addWidget(time_note)
        self.pair_selector.currentIndexChanged.connect(self.select_pair)
        self.select_pair(0)
        available = self.screen().availableGeometry()
        self.resize(min(1500, available.width()), min(1000, available.height()))

    def select_pair(self, index):
        if self._closed:
            return
        if type(index) is not int or not 0 <= index < len(self.pairs):
            raise ValueError("Invalid admitted pair index.")
        self.control_panel.cancel_partial()
        self.kp0_panel.cancel_partial()
        self.current_pair = self.pairs[index]
        p = self.current_pair
        self.control_panel.load_trace(p.control, p.control_facts)
        self.kp0_panel.load_trace(p.kp0, p.kp0_facts)
        blocked = self.pair_selector.blockSignals(True)
        self.pair_selector.setCurrentIndex(index)
        self.pair_selector.blockSignals(blocked)
        identity = p.identity
        self.identity_label.setText(f"Accepted E1: {identity.run_id} · repetition {identity.repetition} · "
                                    f"first click {identity.first_click} · independent physical input sequences")
        self.fingerprint_label.setText("Same board fingerprint (CONTROL = K-P0): " + identity.board_fingerprint)
        d = p.difference
        self.difference_heading.setText(d.label + " — " + d.direction)
        signed = lambda value: f"{value:+,}" if value else "0"
        cost = "N/A" if d.model_c_us is None else signed(d.model_c_us) + " µs"
        self.difference_label.setText(f"Δ Inputs {signed(d.total_inputs)} · Δ OPEN {signed(d.open_inputs)} · "
                                      f"Δ FLAG {signed(d.flag_inputs)} · Δ CHORD {signed(d.chord_inputs)} · Δ Model C {cost}")
        self.difference_note.setText(LOSS_TIME_NOTE if d.model_c_us is None else "Recorded arithmetic difference only.")

    def closeEvent(self, event):
        super().closeEvent(event)
        if event.isAccepted() and not self._closed:
            self.control_panel.shutdown()
            self.kp0_panel.shutdown()
            self._closed = True
            self.closed.emit()
