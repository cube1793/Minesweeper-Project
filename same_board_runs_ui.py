"""Read-only results of a multi-algorithm Same-board Comparison.

Every executed algorithm keeps its own row in the fixed registry order, keyed by
its ID, so arrival order never matters. "Shown result" only changes which
already validated stream is replayed on the fixed board; it never starts a
worker or calls a decision function. Index playback applies the recorded
OPEN/FLAG/CHORD moves on a fresh fixed-layout engine. Model C totals are shown
in the table only; the timed Human/Stage 2/Stage 3 playback stays in the
existing comparison window.
"""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView, QComboBox, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSlider, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from core_engine import Action, MinesweeperEngine
from replay_player import ReplayPlayer
from same_board_algorithms import (
    ALGORITHMS, LABELS, TIME_DEPENDENCE_NOTE, AlgorithmMove, AlgorithmRun, settings_for,
)
from stage3_visualizer_ui import CELL_SIZE, Stage3VisualizerCell


HUMAN = "HUMAN"
COLUMNS = ("Run", "Outcome", "Actions", "OPEN", "FLAG", "CHORD", "Model C time (s)", "Settings", "Note")
RANKING_NOTE = ("Model C time is the original model's time through termination (losses included). "
                "It is not a speed ranking. Outcomes LIMIT, CANCELLED, ERROR and STOPPED are not wins or losses.")


def legacy_runs(execution):
    """Stage 2 / Stage 3 of an accepted SameBoardExecution as display rows."""
    if execution is None:
        return {}
    rows = {}
    for key, traces, metrics in (
        ("S2", execution.stage2_traces, execution.stage2_metrics),
        ("S3", execution.stage3_result.traces, execution.stage3_metrics),
    ):
        moves = tuple(AlgorithmMove(t.move.action.name, t.move.x, t.move.y, t.status_after.name)
                      for t in traces)
        rows[key] = AlgorithmRun(key, metrics.outcome.name, moves, settings_for(key),
                                 "Existing comparison path", metrics.actions,
                                 metrics.model_c_total_us, None, True)
    return rows


class _MovePlayer:
    """Index k means moves[:k] applied to a fresh fixed-layout engine."""

    def __init__(self, board, moves):
        self.board, self.moves = board, tuple(moves)
        self.index = 0
        self.engine = self._fresh()

    def _fresh(self):
        board = self.board
        engine = MinesweeperEngine(board.width, board.height, board.num_mines)
        engine.reset_with_mines(board.width, board.height, board.num_mines, board.mine_positions)
        return engine

    @property
    def count(self):
        return len(self.moves)

    def go_to(self, index):
        engine = self._fresh()
        for move in self.moves[:index]:
            engine.step(move.x, move.y, Action[move.action])
        self.engine, self.index = engine, index

    def observation(self):
        return self.engine.get_observation()

    def status(self):
        return self.engine.status.name


class _HumanPlayer:
    def __init__(self, replay):
        self.player = ReplayPlayer(replay)

    @property
    def count(self):
        return self.player.event_count

    @property
    def index(self):
        return self.player.current_index

    def go_to(self, index):
        self.player.go_to(index)

    def observation(self):
        return self.player.get_observation()

    def status(self):
        return self.player.engine.status.name


class SameBoardRunsWindow(QWidget):
    closed = pyqtSignal()
    legacy_requested = pyqtSignal()

    def __init__(self, context, runs, execution=None, parent=None):
        super().__init__(parent, Qt.Window)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle("Same-board Comparison — Algorithms")
        self.context, self.execution = context, execution
        merged = dict(legacy_runs(execution))
        merged.update(runs)
        # Fixed registry order, never arrival order.
        self.runs = {key: merged[key] for key in ALGORITHMS if key in merged}
        self._closed = False
        board = context.layout.board
        self.players = {HUMAN: _HumanPlayer(context.human_replay)}
        for key, run in self.runs.items():
            if run.playable:
                self.players[key] = _MovePlayer(board, run.moves)
        self.positions = {key: 0 for key in self.players}

        layout = QVBoxLayout(self)
        note = QLabel(RANKING_NOTE)
        note.setWordWrap(True)
        layout.addWidget(note)
        self.table = QTableWidget(1 + len(self.runs), len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self._fill_table()
        layout.addWidget(self.table)

        selection = QHBoxLayout()
        selection.addWidget(QLabel("Shown result:"))
        self.shown_selector = QComboBox()
        self.shown_selector.setAccessibleName("Shown result")
        self.shown_selector.addItem("Human", HUMAN)
        for key in self.runs:
            if key in self.players:
                self.shown_selector.addItem(LABELS[key], key)
        self.shown_selector.currentIndexChanged.connect(self.on_shown_changed)
        selection.addWidget(self.shown_selector)
        self.status_label = QLabel("")
        selection.addWidget(self.status_label, 1)
        self.legacy_button = QPushButton("Open Stage 2 / Stage 3 detail")
        self.legacy_button.setVisible(execution is not None)
        self.legacy_button.clicked.connect(self.legacy_requested.emit)
        selection.addWidget(self.legacy_button)
        layout.addLayout(selection)

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
        scroll = QScrollArea()
        scroll.setWidget(self.board_container)
        scroll.setWidgetResizable(False)
        scroll.setMinimumSize(100, 100)
        layout.addWidget(scroll, 1)

        controls = QHBoxLayout()
        for name, text, handler in (("first_button", "First", lambda: self._seek(0)),
                                    ("previous_button", "Previous", lambda: self._seek(self._index() - 1)),
                                    ("next_button", "Next", lambda: self._seek(self._index() + 1)),
                                    ("last_button", "Last", lambda: self._seek(self._player().count))):
            button = QPushButton(text)
            button.clicked.connect(handler)
            setattr(self, name, button)
            controls.addWidget(button)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setAccessibleName("Shown result action index")
        self.slider.valueChanged.connect(self._seek)
        controls.addWidget(self.slider, 1)
        self.index_label = QLabel()
        controls.addWidget(self.index_label)
        layout.addLayout(controls)
        self.refresh()
        self.resize(min(1200, max(760, board.width * CELL_SIZE + 60)), 760)

    def _fill_table(self):
        human = self.context.human_replay.events
        counts = {name: sum(event.action == name for event in human) for name in ("OPEN", "FLAG", "CHORD")}
        rows = [("Human", self.context.terminal_status.name, len(human), counts["OPEN"], counts["FLAG"],
                 counts["CHORD"], "—", "recorded Replay", "Replay time is not Model C time")]
        for run in self.runs.values():
            actions = run.actions
            model = "—" if run.model_c_total_us is None else f"{run.model_c_total_us / 1e6:.3f}"
            notes = [text for text in (run.detail, TIME_DEPENDENCE_NOTE if run.time_dependent else "") if text]
            rows.append((run.label, run.outcome,
                         "—" if actions is None else actions.semantic_action_count,
                         "—" if actions is None else actions.open_count,
                         "—" if actions is None else actions.flag_input_count,
                         "—" if actions is None else actions.chord_count, model,
                         "; ".join(f"{key}: {value}" for key, value in run.settings), " | ".join(notes)))
        for row, values in enumerate(rows):
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()

    def shown_key(self):
        return self.shown_selector.currentData()

    def _player(self):
        return self.players[self.shown_key()]

    def _index(self):
        return self.positions[self.shown_key()]

    def _seek(self, index):
        if self._closed:
            return
        player = self._player()
        index = max(0, min(player.count, int(index)))
        if player.index != index:
            player.go_to(index)
        self.positions[self.shown_key()] = index
        self.refresh()

    def on_shown_changed(self, _index):
        player = self._player()
        if player.index != self._index():
            player.go_to(self._index())
        self.refresh()

    def refresh(self):
        if self._closed:
            return
        player, index = self._player(), self._index()
        for y, row in enumerate(player.observation()):
            for x, value in enumerate(row):
                self.cells[x, y].render_state(value)
        key = self.shown_key()
        outcome = "recorded Human game" if key == HUMAN else f"outcome {self.runs[key].outcome}"
        self.status_label.setText(f"{LABELS.get(key, 'Human')}: board status {player.status()}, {outcome}")
        self.index_label.setText(f"Action index {index} / {player.count}")
        blocked = self.slider.blockSignals(True)
        try:
            self.slider.setRange(0, player.count)
            self.slider.setValue(index)
        finally:
            self.slider.blockSignals(blocked)
        self.first_button.setEnabled(index > 0)
        self.previous_button.setEnabled(index > 0)
        self.next_button.setEnabled(index < player.count)
        self.last_button.setEnabled(index < player.count)

    def closeEvent(self, event):
        super().closeEvent(event)
        if event.isAccepted() and not self._closed:
            self._closed = True
            self.closed.emit()
