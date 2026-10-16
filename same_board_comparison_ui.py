"""Read-only presentation of one completed Same-board Comparison.

Navigation belongs to SameBoardPlayback. This window owns no execution, admission,
process lifecycle or clock; original streams, attachments and metrics stay intact.
"""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSizePolicy, QSlider, QVBoxLayout, QWidget,
)

from mouse_trace_ui import MouseTraceOverlay
from same_board_comparison import STAGE2_CANONICAL_FIRST_ACTION, STAGE3_CANONICAL_FIRST_ACTION
from same_board_playback import ComparisonRun, SameBoardPlayback
from same_board_runner import SameBoardExecution
from stage3_visualizer_ui import CELL_SIZE, Stage3VisualizerCell


class SameBoardComparisonWindow(QWidget):
    """One result, three independent indices, one public-observation board."""

    closed = pyqtSignal()

    def __init__(self, execution: SameBoardExecution, parent=None):
        super().__init__(parent, Qt.Window)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle("Same-board Comparison")
        self.execution = execution
        self.playback = SameBoardPlayback(execution)
        self._closed = False
        layout = QVBoxLayout(self)

        facts = QHBoxLayout()
        facts.addWidget(self._build_summary(), 1)
        facts.addWidget(self._build_qualification(), 1)
        layout.addLayout(facts)
        self.caveat_label = self._label(
            "Same layout or matching recorded start does not establish identical historical "
            "mine placement, execution semantics, exclusively-Human provenance, or a controlled experiment."
        )
        layout.addWidget(self.caveat_label)

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
        self.mouse_trace_overlay = MouseTraceOverlay(self.board_container)
        replay = execution.context.human_replay
        self.mouse_trace_overlay.set_trace(replay.mouse_trace, replay.events)
        self.mouse_trace_overlay.set_cell_size(CELL_SIZE)
        self.mouse_trace_overlay.setGeometry(self.board_container.rect())
        self.mouse_trace_overlay.raise_()
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.board_container)
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.scroll_area.setMinimumSize(100, 100)
        layout.addWidget(self.scroll_area, 1)

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
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setAccessibleName("Selected run action index")
        self.slider.valueChanged.connect(self.on_slider_changed)
        controls.addWidget(self.slider, 1)
        self.index_label = QLabel()
        controls.addWidget(self.index_label)
        layout.addLayout(controls)

        self.mouse_trace_checkbox = QCheckBox("Show Human Mouse Trace (entire recording)")
        self.mouse_trace_checkbox.setToolTip(
            "Entire recorded Human path; independent of the current action index."
        )
        self.mouse_trace_checkbox.toggled.connect(self._update_mouse_trace)
        layout.addWidget(self.mouse_trace_checkbox)
        self.refresh()
        available = self.screen().availableGeometry()
        self.resize(min(1120, available.width()),
                    min(board.height * CELL_SIZE + 480, available.height()))

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
        self._update_mouse_trace()

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
        try:
            operation()
        except Exception as exc:
            error = exc
        # On failure, resynchronize widgets with the player's committed state.
        # Do not seek to repair it or reinterpret an exception as an outcome.
        try:
            self.refresh()
        except Exception as exc:
            error = error if error is not None else exc
        if error is None:
            self.error_label.clear()
            self.error_label.hide()
        else:
            self.error_label.setText(f"Playback error: {error}")
            self.error_label.show()

    def on_run_changed(self, _index):
        self._navigate(lambda: self.playback.select(self.run_selector.currentData()))

    def on_first(self):
        self._navigate(lambda: self.playback.go_to(0))

    def on_previous(self):
        self._navigate(self.playback.previous)

    def on_next(self):
        self._navigate(self.playback.next)

    def on_last(self):
        self._navigate(lambda: self.playback.go_to(self.playback.action_count()))

    def on_slider_changed(self, index):
        self._navigate(lambda: self.playback.go_to(index))

    def closeEvent(self, event):
        super().closeEvent(event)
        if event.isAccepted() and not self._closed:
            self._closed = True
            self.closed.emit()
