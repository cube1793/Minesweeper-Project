"""Read-only presentation of one completed Same-board Comparison.

Committed board navigation belongs to SameBoardPlayback. Independent pure timing
controllers supply presentation progress; this window owns only widgets and one
presentation timer. Original streams, attachments and metrics stay intact.
"""

from fractions import Fraction
from time import monotonic_ns

from PyQt5.QtCore import QEvent, QPointF, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPen, QValidator
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSizePolicy, QSlider, QSpinBox, QDoubleSpinBox, QStyle,
    QStyleOptionSlider, QStyleOptionSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from core_engine import CellState
from mouse_trace_ui import MouseTraceOverlay
from same_board_comparison import STAGE2_CANONICAL_FIRST_ACTION, STAGE3_CANONICAL_FIRST_ACTION
from same_board_playback import ComparisonRun, SameBoardPlayback
from same_board_runner import SameBoardExecution
from same_board_timed_playback import PlaybackMode, SameBoardTimedPlayback, project_same_board_timings
from stage3_visualizer_ui import CELL_SIZE, Stage3VisualizerCell
from visualization_reference_overlays import (
    derive_answer_clues, paint_hidden_answers, paint_action_target_route,
)


CURSOR_NOTE = ('Synthetic smooth interpolation between executed action targets. '
               'Not recorded mouse motion or an actual OS cursor trajectory. '
               'Easing is presentation only, not calibrated acceleration.')
ROUTE_NOTE = 'Action-target route — not recorded cursor trajectory'


class _IndexSlider(QSlider):
    """Direct empty-track seek; native Qt still owns handle dragging."""
    track_seek = pyqtSignal(int)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            option = QStyleOptionSlider()
            self.initStyleOption(option)
            handle = self.style().subControlRect(
                QStyle.CC_Slider, option, QStyle.SC_SliderHandle, self)
            if not handle.contains(event.pos()):
                span = max(1, self.width() - handle.width())
                position = max(0, min(span, event.x() - handle.width() // 2))
                self.track_seek.emit(QStyle.sliderValueFromPosition(
                    self.minimum(), self.maximum(), position, span, option.upsideDown))
                event.accept()
                return
        super().mousePressEvent(event)


class _IndexInterval(QSpinBox):
    """Local integer commit/clamp and compact native-style sizing."""
    def validate(self, text, pos):
        value = text.removesuffix(self.suffix()).strip()
        try:
            integer = int(value)
        except ValueError:
            if value in ('-', '+'):
                return QValidator.Intermediate, text, pos
        else:
            if not self.minimum() <= integer <= self.maximum():
                return QValidator.Intermediate, text, pos
        return super().validate(text, pos)

    def fixup(self, text):
        try:
            value = int(text.removesuffix(self.suffix()).strip())
        except ValueError:
            return super().fixup(text)
        return str(max(self.minimum(), min(self.maximum(), value))) + self.suffix()

    def fit_text_width(self):
        option = QStyleOptionSpinBox()
        self.initStyleOption(option)
        metrics = self.fontMetrics()
        width = max(metrics.horizontalAdvance(self.specialValueText()),
                    metrics.horizontalAdvance(str(self.maximum()) + self.suffix()))
        margin = metrics.horizontalAdvance('  ') + self.style().pixelMetric(
            QStyle.PM_DefaultFrameWidth, option, self)
        size = self.style().sizeFromContents(
            QStyle.CT_SpinBox, option, QSize(width + margin, metrics.height()), self)
        self.setFixedWidth(size.width())

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.FontChange, QEvent.StyleChange, QEvent.ApplicationFontChange):
            self.fit_text_width()


class _Overlay(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.NoFocus)

    @staticmethod
    def center(target):
        return QPointF((target[0] + 0.5) * CELL_SIZE, (target[1] + 0.5) * CELL_SIZE)


class _AnswerOverlay(_Overlay):
    def __init__(self, parent, answers, font):
        super().__init__(parent)
        self.answers, self.answer_font = answers, font
        self.hidden_mask = ()

    def paintEvent(self, event):
        if self.hidden_mask:
            painter = QPainter(self)
            paint_hidden_answers(painter, self.answers, self.hidden_mask, CELL_SIZE, self.answer_font)


class _RouteOverlay(_Overlay):
    def __init__(self, parent):
        super().__init__(parent)
        self.targets = ()

    def paintEvent(self, event):
        painter = QPainter(self)
        paint_action_target_route(painter, [self.center(target) for target in self.targets])


class _ContextCursorOverlay(_Overlay):
    def __init__(self, parent):
        super().__init__(parent)
        self.previous_target = self.current_target = None
        self.cursor_center = QPointF()

    @classmethod
    def interpolated_center(cls, start, end, progress):
        u = max(0.0, min(1.0, float(progress)))
        q = u * u * (3 - 2 * u)
        a, b = cls.center(start), cls.center(end)
        return a + (b - a) * q

    def set_cursor(self, state):
        point = self.interpolated_center(state.segment_start, state.segment_end, state.progress)
        if point != self.cursor_center:
            previous, self.cursor_center = self.cursor_center, point
            for center in (previous, point):
                self.update(QRectF(center.x() - 12, center.y() - 12, 24, 24).toAlignedRect())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(Qt.NoBrush)
        previous, current = self.previous_target, self.current_target
        if previous is not None:
            if previous != current:
                painter.setPen(QPen(QColor('white'), 4))
                painter.drawLine(self.center(previous), self.center(current))
                painter.setPen(QPen(QColor('#2463c5'), 2))
                painter.drawLine(self.center(previous), self.center(current))
            painter.setPen(QPen(QColor('#2463c5'), 2))
            painter.drawEllipse(self.center(previous), 8, 8)
        if current is not None:
            x, y = current
            painter.setPen(QPen(QColor('#cc7000'), 2))
            painter.drawRect(x * CELL_SIZE + 2, y * CELL_SIZE + 2, CELL_SIZE - 4, CELL_SIZE - 4)
        painter.setPen(QPen(QColor('white'), 4))
        painter.drawEllipse(self.cursor_center, 9, 9)
        painter.setPen(QPen(QColor('#007a58'), 2))
        painter.drawEllipse(self.cursor_center, 9, 9)


class SameBoardComparisonWindow(QWidget):
    """One result, three independent indices, one public-observation board."""

    closed = pyqtSignal()

    def __init__(self, execution: SameBoardExecution, parent=None, *, clock=monotonic_ns):
        super().__init__(parent, Qt.Window)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle("Same-board Comparison")
        self.execution = execution
        self.playback = SameBoardPlayback(execution)
        timings = project_same_board_timings(execution)
        self.controllers = {
            run: SameBoardTimedPlayback(timing, clock=clock) for run, timing in zip(
                ComparisonRun, (timings.human, timings.stage2, timings.stage3))
        }
        self.presentation_timer = QTimer(self)
        self.presentation_timer.setInterval(16)
        self.presentation_timer.timeout.connect(self.on_tick)
        self._closed = False
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        summary = QWidget()
        facts = QVBoxLayout(summary)
        facts.addWidget(self._build_summary())
        self.caveat_label = self._label(
            "Same layout or matching recorded start does not establish identical historical "
            "mine placement, execution semantics, exclusively-Human provenance, or a controlled experiment."
        )
        facts.addWidget(self.caveat_label)
        facts.addStretch()

        selection = QHBoxLayout()
        selection.addWidget(QLabel("Run:"))
        self.run_selector = QComboBox()
        self.run_selector.setAccessibleName("Comparison run")
        self.run_selector.addItem("Human", ComparisonRun.HUMAN)
        self.run_selector.addItem("Stage 2", ComparisonRun.STAGE2)
        self.run_selector.addItem("Stage 3", ComparisonRun.STAGE3)
        self.run_selector.currentIndexChanged.connect(self.on_run_changed)
        selection.addWidget(self.run_selector)
        self.status_label = self._label("")
        selection.addWidget(self.status_label, 1)
        layout.addLayout(selection)
        self.error_label = self._label("")
        self.error_label.setStyleSheet("color: #c00000;")
        self.error_label.hide()
        layout.addWidget(self.error_label)

        board = execution.context.layout.board
        self.board_container = QWidget()
        grid = QGridLayout(self.board_container)
        grid.setSpacing(0)
        grid.setContentsMargins(0, 0, 0, 0)
        self.cells = {}
        for y in range(board.height):
            for x in range(board.width):
                cell = Stage3VisualizerCell(x, y, self.board_container)
                self.cells[x, y] = cell
                grid.addWidget(cell, y, x)
        self.board_container.setFixedSize(board.width * CELL_SIZE, board.height * CELL_SIZE)
        answers = derive_answer_clues(board.width, board.height, board.mine_positions)
        self.answer_overlay = _AnswerOverlay(self.board_container, answers, self.cells[0, 0].font())
        self.route_overlay = _RouteOverlay(self.board_container)
        self.mouse_trace_overlay = MouseTraceOverlay(self.board_container)
        replay = execution.context.human_replay
        self.mouse_trace_overlay.set_trace(replay.mouse_trace, replay.events)
        self.mouse_trace_overlay.set_cell_size(CELL_SIZE)
        self.mouse_trace_overlay.setGeometry(self.board_container.rect())
        self.context_overlay = _ContextCursorOverlay(self.board_container)
        # Creation/raise order is explicit: references < actual trace < context/cursor.
        self.overlay_layers = (self.answer_overlay, self.route_overlay,
                               self.mouse_trace_overlay, self.context_overlay)
        for overlay in self.overlay_layers:
            overlay.setGeometry(self.board_container.rect())
            overlay.raise_()
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.board_container)
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.scroll_area.setMinimumSize(100, 100)
        self.tabs.addTab(self.scroll_area, 'Board')
        for caption, widget in (('Summary', summary), ('Recorded opening', self._build_qualification())):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(widget)
            self.tabs.addTab(scroll, caption)
        layout.addWidget(self.tabs, 1)

        controls = QHBoxLayout()
        for name, text, handler in (
            ("first_button", "First", self.on_first),
            ("previous_button", "Previous", self.on_previous),
            ("next_button", "Next", self.on_next),
            ("last_button", "Last", self.on_last),
        ):
            button = QPushButton(text)
            button.clicked.connect(handler)
            setattr(self, name, button)
            controls.addWidget(button)
        self.slider = _IndexSlider(Qt.Horizontal)
        self.slider.setAccessibleName("Selected run action index")
        self.slider.valueChanged.connect(self.on_slider_changed)
        self.slider.track_seek.connect(self.on_slider_changed)
        # A click without an index change is inert, including on the handle.
        # The first actual drag/value change takes the ordinary manual-seek path.
        controls.addWidget(self.slider, 1)
        self.index_label = QLabel()
        controls.addWidget(self.index_label)
        layout.addLayout(controls)

        timing_controls = QHBoxLayout()
        self.play_button = QPushButton('Play')
        self.play_button.clicked.connect(self.on_play_pause)
        timing_controls.addWidget(self.play_button)
        self.mode_selector = QComboBox()
        self.mode_selector.setAccessibleName('Selected run playback mode')
        self.mode_selector.currentIndexChanged.connect(self.on_mode_changed)
        timing_controls.addWidget(self.mode_selector)
        timing_controls.addWidget(QLabel('Interval:'))
        self.interval_entry = _IndexInterval()
        self.interval_entry.setRange(20, 5000)
        self.interval_entry.setValue(200)
        self.interval_entry.setSuffix(' ms')
        self.interval_entry.setSpecialValueText('Max (20 ms)')
        self.interval_entry.setKeyboardTracking(False)
        self.interval_entry.setAccessibleName('Index presentation interval')
        self.interval_entry.fit_text_width()
        self.interval_entry.valueChanged.connect(self.on_interval_changed)
        timing_controls.addWidget(self.interval_entry)
        timing_controls.addWidget(QLabel('Playback speed:'))
        self.speed_entry = QDoubleSpinBox()
        self.speed_entry.setRange(0.25, 8)
        self.speed_entry.setSingleStep(0.25)
        self.speed_entry.setValue(1)
        self.speed_entry.setSuffix('x')
        self.speed_entry.setKeyboardTracking(False)
        self.speed_entry.setAccessibleName('Time playback speed')
        self.speed_entry.valueChanged.connect(self.on_speed_changed)
        timing_controls.addWidget(self.speed_entry)
        timing_controls.addStretch()
        layout.addLayout(timing_controls)
        self.playback_label = self._label('')
        self.playback_label.setToolTip(
            'Independent selected-run presentation. The 16 ms refresh request is not a time authority. '
            'The board and route remain at the completed prefix during partial motion. '
            'Green hollow ring: synthetic cursor. Orange: last completed target; '
            'blue: previous target/transition. ' + CURSOR_NOTE)
        layout.addWidget(self.playback_label)

        references = QHBoxLayout()
        self.answer_checkbox = QCheckBox('Show hidden answers')
        self.answer_checkbox.setToolTip('Faint fixed-board reference on public HIDDEN cells only.')
        self.answer_checkbox.toggled.connect(self._update_references)
        references.addWidget(self.answer_checkbox)
        self.route_checkbox = QCheckBox('Show action-target route')
        self.route_checkbox.setToolTip(ROUTE_NOTE + '. Completed targets only; no future targets.')
        self.route_checkbox.toggled.connect(self._update_references)
        references.addWidget(self.route_checkbox)
        references.addStretch()
        layout.addLayout(references)

        self.mouse_trace_checkbox = QCheckBox("Show Human Mouse Trace (entire recording)")
        self.mouse_trace_checkbox.setToolTip(
            "Entire recorded Human path; independent of the current action index."
        )
        self.mouse_trace_checkbox.toggled.connect(self._update_mouse_trace)
        self.mouse_trace_checkbox.setToolTip(self.mouse_trace_checkbox.toolTip() +
            ' Separate from the purple action-target route and green synthetic cursor.')
        layout.addWidget(self.mouse_trace_checkbox)
        self.refresh()
        available = self.screen().availableGeometry()
        self.resize(min(1120, available.width()),
                    min(board.height * CELL_SIZE + 280, available.height()))

    @staticmethod
    def _label(text):
        label = QLabel(text)
        label.setTextFormat(Qt.PlainText)
        label.setWordWrap(True)
        # Facts wrap to the available width instead of forcing the board's
        # scroll viewport wider than a small screen/window.
        policy = label.sizePolicy()  # Preserve word-wrap's height-for-width flag.
        policy.setHorizontalPolicy(QSizePolicy.Ignored)
        label.setSizePolicy(policy)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        return label

    def _build_summary(self):
        box = QGroupBox("Summary")
        grid = QGridLayout(box)
        grid.setColumnStretch(0, 2)
        for column, caption in enumerate(("Human", "Stage 2", "Stage 3"), 1):
            grid.setColumnStretch(column, 1)
            grid.addWidget(QLabel(caption), 0, column)
        human, stage2, stage3 = (
            self.execution.human_metrics, self.execution.stage2_metrics, self.execution.stage3_metrics,
        )
        metrics = (human, stage2, stage3)
        rows = (
            ("Final outcome", tuple(m.outcome.name for m in metrics)),
            ("Semantic actions", tuple(str(m.actions.semantic_action_count) for m in metrics)),
            ("OPEN inputs", tuple(str(m.actions.open_count) for m in metrics)),
            ("FLAG inputs (incl. unflag)", tuple(str(m.actions.flag_input_count) for m in metrics)),
            ("CHORD inputs", tuple(str(m.actions.chord_count) for m in metrics)),
            ("Human Replay elapsed", (f"{human.replay_elapsed_seconds} s", "—", "—")),
            ("Model C cost through termination", ("—", f"{stage2.model_c_total_us:,} µs",
                                                  f"{stage3.model_c_total_us:,} µs")),
            ("Decision compute total", ("—", f"{stage2.decision_compute_total_ns:,} ns",
                                           f"{stage3.decision_compute_total_ns:,} ns")),
        )
        self.summary_labels = {}
        for row, (caption, values) in enumerate(rows, 1):
            grid.addWidget(self._label(caption), row, 0)
            labels = tuple(self._label(value) for value in values)
            self.summary_labels[caption] = labels
            for column, label in enumerate(labels, 1):
                grid.addWidget(label, row, column)
        box.setToolTip(
            "Recorded elapsed, modeled cost and decision compute are separate authorities. "
            "Compute totals sum recorded non-None measurements; canonical first inputs have no decision measurement."
        )
        return box

    def _build_qualification(self):
        box = QGroupBox("Recorded opening")
        layout = QVBoxLayout(box)
        context = self.execution.context
        first, opened = context.first_event, context.first_open_event
        first_text = "none" if first is None else f"{first.action} ({first.x}, {first.y})"
        open_text = "none" if opened is None else (
            f"({opened.x}, {opened.y}); zero-based Replay event index {context.first_open_event_index}"
        )
        if context.matches_canonical_recorded_start:
            match = "yes — Human event 0 is OPEN (0, 0)."
        elif opened is None:
            match = "no — no Human OPEN was recorded."
        else:
            reasons = []
            if context.has_prelude_events:
                reasons.append("prelude before first OPEN")
            if (opened.x, opened.y) != (0, 0):
                reasons.append(f"first OPEN targets ({opened.x}, {opened.y})")
            match = "no — " + "; ".join(reasons) + "."
        s2, s3 = STAGE2_CANONICAL_FIRST_ACTION, STAGE3_CANONICAL_FIRST_ACTION
        self.qualification_label = self._label(
            "Exact same fixed layout verified.\n"
            f"Human first recorded event: {first_text}\n"
            f"Human first OPEN: {open_text}\n"
            f"Prelude before first OPEN: {'yes' if context.has_prelude_events else 'no'}\n"
            f"Stage 2 first action: {s2[0]} ({s2[1]}, {s2[2]})\n"
            f"Stage 3 first action: {s3[0]} ({s3[1]}, {s3[2]})\n"
            f"Solver origin (0, 0): {'mine' if context.solver_origin_is_mine else 'not a mine'}\n"
            f"Matching recorded start: {match}"
        )
        layout.addWidget(self.qualification_label)
        if context.solver_origin_is_mine:
            layout.addWidget(self._label(
                "This is an already-fixed layout; ordinary fresh-game first-OPEN placement safety does not apply."
            ))
        layout.addStretch()
        return box

    def refresh(self):
        """Read and render only; synchronizing widgets never navigates a player."""
        if self._closed:
            return
        playback = self.playback
        run, index, count = playback.selected_run, playback.current_index, playback.action_count()
        observation = playback.get_observation()
        status = playback.status
        for y, row in enumerate(observation):
            for x, value in enumerate(row):
                self.cells[x, y].render_state(value)
        if self.controller.state.completed_index != index:
            self.controller.align(index)
        self.answer_overlay.hidden_mask = tuple(tuple(value == CellState.HIDDEN for value in row)
                                                for row in observation)
        targets = self.controller.timing.targets
        self.route_overlay.targets = targets[:index]
        self.context_overlay.current_target = targets[index - 1] if index else None
        self.context_overlay.previous_target = targets[index - 2] if index > 1 else None
        self.context_overlay.update()
        self.status_label.setText(f"Current reconstructed status: {status.name}")
        self.index_label.setText(f"Action index {index} / {count}")
        blocked = self.run_selector.blockSignals(True)
        try:
            self.run_selector.setCurrentIndex(self.run_selector.findData(run))
        finally:
            self.run_selector.blockSignals(blocked)
        blocked = self.slider.blockSignals(True)
        try:
            self.slider.setRange(0, count)
            self.slider.setValue(index)
        finally:
            self.slider.blockSignals(blocked)
        self.first_button.setEnabled(index > 0)
        self.previous_button.setEnabled(index > 0)
        self.next_button.setEnabled(index < count)
        self.last_button.setEnabled(index < count)
        self._sync_configuration()
        self._update_presentation()
        self._update_references()
        self._update_mouse_trace()

    @property
    def controller(self):
        return self.controllers[self.playback.selected_run]

    def _sync_configuration(self, *, reset_edits=False):
        controller = self.controller
        modes = (PlaybackMode.INDEX, PlaybackMode(controller.timing.authority.value))
        widgets = (self.mode_selector, self.interval_entry, self.speed_entry)
        blocked = [widget.blockSignals(True) for widget in widgets]
        try:
            if tuple(self.mode_selector.itemData(i) for i in range(self.mode_selector.count())) != modes:
                self.mode_selector.clear()
                for mode in modes:
                    self.mode_selector.addItem(mode.value, mode)
            self.mode_selector.setCurrentIndex(self.mode_selector.findData(controller.state.mode))
            # A board boundary must not overwrite uncommitted editor text while
            # the user changes a running interval/speed. Run changes reset it.
            if reset_edits or self.interval_entry.value() != controller.interval_ms:
                self.interval_entry.setValue(controller.interval_ms)
            if reset_edits or self.speed_entry.value() != float(controller.speed):
                self.speed_entry.setValue(float(controller.speed))
        finally:
            for widget, previous in zip(widgets, blocked):
                widget.blockSignals(previous)
        is_index = controller.state.mode is PlaybackMode.INDEX
        self.interval_entry.setEnabled(is_index)
        self.speed_entry.setEnabled(not is_index)

    def _update_presentation(self):
        """No board observation/render, reference-prefix work or clock read here."""
        state = self.controller.state
        self.context_overlay.set_cursor(state)
        self.play_button.setText('Pause' if state.running else 'Play')
        self.play_button.setEnabled(not state.terminal)
        if state.mode is PlaybackMode.INDEX:
            interval = self.controller.interval_ms
            rate = 'Max (20 ms/action)' if interval == 20 else f'{interval} ms/action'
            text = f'Index — {rate}'
        else:
            # Formatting is presentation only, never fed back to exact timing.
            divisor = 1_000_000 if state.mode is PlaybackMode.MODEL_C_TIME else 1
            text = (f'{state.mode.value} — {float(self.controller.speed):g}x — '
                    f'{float(state.playhead / divisor):.6f} / '
                    f'{float(self.controller.timing.total_time / divisor):.6f} s')
        self.playback_label.setText(text + ' • Synthetic action-target cursor')
        if not state.running:
            self.presentation_timer.stop()

    def _update_references(self, _checked=None):
        if self._closed:
            return
        self.answer_overlay.setVisible(self.answer_checkbox.isChecked())
        self.route_overlay.setVisible(self.route_checkbox.isChecked())
        self.answer_overlay.update()
        self.route_overlay.update()

    def _update_mouse_trace(self, _checked=None):
        if self._closed:
            return
        available = (self.playback.selected_run is ComparisonRun.HUMAN
                     and self.execution.context.human_replay.mouse_trace is not None)
        self.mouse_trace_checkbox.setEnabled(available)
        self.mouse_trace_overlay.setVisible(available and self.mouse_trace_checkbox.isChecked())

    def _navigate(self, operation):
        if self._closed:
            return
        error = None
        self.presentation_timer.stop()
        self.controller.align(self.playback.current_index)
        try:
            operation()
        except Exception as exc:
            error = exc
        self.controller.align(self.playback.current_index)
        # On failure, resynchronize widgets with the player's committed state.
        # Do not seek to repair it or reinterpret an exception as an outcome.
        try:
            self.refresh()
        except Exception as exc:
            error = error if error is not None else exc
        self._show_error(error)

    def _show_error(self, error):
        if error is None:
            self.error_label.clear()
            self.error_label.hide()
        else:
            self.error_label.setText(f"Playback error: {error}")
            self.error_label.show()

    def on_run_changed(self, _index):
        if self._closed or self.run_selector.currentData() is self.playback.selected_run:
            return
        # Sample/pause only the old run, applying any newly due prefix before
        # selecting another. Preserve partial presentation if actual index agrees.
        self.presentation_timer.stop()
        requested = self.run_selector.currentData()
        if not self._timed_operation(self.controller.pause):
            self.refresh()
            return
        try:
            self.playback.select(requested)
            if self.controller.state.completed_index != self.playback.current_index:
                self.controller.align(self.playback.current_index)
            self._sync_configuration(reset_edits=True)
            self.refresh()
        except Exception as exc:
            self.controller.align(self.playback.current_index)
            self._show_error(exc)

    def on_first(self):
        self._navigate(lambda: self.playback.go_to(0))

    def on_previous(self):
        self._navigate(self.playback.previous)

    def on_next(self):
        self._navigate(self.playback.next)

    def on_last(self):
        self._navigate(lambda: self.playback.go_to(self.playback.action_count()))

    def on_slider_changed(self, index):
        if index == self.playback.current_index:
            return
        self._navigate(lambda: self.playback.go_to(index))

    def _cancel_partial(self):
        if self._closed:
            return
        self.presentation_timer.stop()
        self.controller.align(self.playback.current_index)
        self._update_presentation()

    def _timed_operation(self, operation):
        if self._closed:
            return False
        try:
            state = operation()  # Exactly one timing sample per callback.
            if state.completed_index != self.playback.current_index:
                self.playback.go_to(state.completed_index)
                self.refresh()  # One board render for the final due prefix.
            else:
                self._update_presentation()
            self._show_error(None)
            return True
        except Exception as exc:
            self.presentation_timer.stop()
            self.controller.align(self.playback.current_index)
            try:
                self.refresh()
            except Exception:
                pass  # Preserve the original bounded playback error.
            self._show_error(exc)
            return False

    def on_tick(self):
        if not self._closed and self.controller.state.running:
            self._timed_operation(self.controller.update)

    def on_play_pause(self):
        if self._closed:
            return
        operation = self.controller.pause if self.controller.state.running else self.controller.play
        if self._timed_operation(operation) and self.controller.state.running:
            self.presentation_timer.start()

    def on_mode_changed(self, _index):
        if self._closed:
            return
        mode = self.mode_selector.currentData()
        self._cancel_partial()
        self._timed_operation(lambda: self.controller.set_mode(mode))
        self._sync_configuration()

    def on_interval_changed(self, value):
        if not self._closed:
            self._timed_operation(lambda: self.controller.set_interval(value))
            self._sync_configuration()

    def on_speed_changed(self, value):
        if not self._closed:
            speed = Fraction(max(1, min(32, round(value * 4))), 4)
            self._timed_operation(lambda: self.controller.set_speed(speed))
            self._sync_configuration()

    def closeEvent(self, event):
        super().closeEvent(event)
        if event.isAccepted() and not self._closed:
            self._closed = True
            self.presentation_timer.stop()
            for controller in self.controllers.values():
                controller.stop()
            self.closed.emit()
