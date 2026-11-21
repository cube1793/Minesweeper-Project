"""Read-only results of a multi-algorithm Same-board Comparison.

Every executed algorithm keeps its own row in the fixed registry order, keyed by
its ID, so arrival order never matters. The shown-result choice only changes
which already validated stream is replayed on the fixed board; it never starts a
worker or calls a decision function. Index playback applies the recorded
OPEN/FLAG/CHORD moves on a fresh fixed-layout engine; Index autoplay advances
one action per interval (the existing detail window's defaults, range and stop
rules). Model C totals are shown in the summary only; the timed Human/Stage 2/
Stage 3 playback stays in the existing comparison window. Statistics come from
the existing Replay statistics code (``same_board_statistics``). The hidden
answer reference is presentation only, drawn on public HIDDEN cells.
"""

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSizePolicy, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from core_engine import Action, CellState, MinesweeperEngine
from replay_player import ReplayPlayer
from same_board_algorithms import (
    ALGORITHMS, LABELS, TIME_DEPENDENCE_NOTE, AlgorithmMove, AlgorithmRun, settings_for,
)
from same_board_comparison_ui import _AnswerOverlay, _ComparisonCell, _IndexInterval, _IndexSlider
from same_board_statistics import NOTE as STATISTICS_NOTE, STAT_LABELS, algorithm_statistics, human_statistics
from same_board_timed_playback import (
    INDEX_INTERVAL_DEFAULT_MS, INDEX_INTERVAL_MAX_MS, INDEX_INTERVAL_MIN_MS,
)
from stage3_visualizer_ui import CELL_SIZE
from visualization_reference_overlays import derive_answer_clues


HUMAN = "HUMAN"
COLUMNS = ("실행", "결과", "3BV", "행동 수", "Efficiency", "IOE", "Model C 시간 (s)")
OUTCOME_NAMES = {
    "WON": "승리", "LOST": "패배", "STOPPED": "정책이 입력 없이 멈춤", "LIMIT": "시간 한도",
    "CANCELLED": "취소", "ERROR": "오류",
}
BOARD_STATUS_NAMES = {"PLAYING": "진행 중", "WON": "승리", "LOST": "패배"}
RANKING_NOTE = (
    "Model C 시간은 원 Model C 기준으로 종료까지(패배 포함) 계산한 모델 시간입니다. 속도 순위가 아닙니다.\n"
    "결과: WON 승리 · LOST 패배 · STOPPED 정책이 입력 없이 멈춤 · LIMIT 시간 한도 · CANCELLED 취소 · "
    "ERROR 오류. LIMIT·CANCELLED·ERROR·STOPPED는 승리나 패배가 아닙니다.\n"
    "표에서 행을 고르면 아래에 그 결과의 설정과 설명이 보입니다."
)
HUMAN_DETAIL = "기록된 Replay입니다. Replay 시간은 Model C 시간이 아닙니다."
LEGACY_DETAIL = "기존 비교 경로로 실행(Stage 2 / Stage 3 상세 창과 같은 결과)"
ANSWER_TOOLTIP = "고정 배치의 정답을 공개 상태가 HIDDEN인 칸에만 흐리게 보여 줍니다. 표시 전용입니다."


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
                                 LEGACY_DETAIL, metrics.actions,
                                 metrics.model_c_total_us, None, True)
    return rows


def _text_label(text=""):
    """Plain wrapped text that follows the window width instead of widening it."""
    label = QLabel(text)
    label.setTextFormat(Qt.PlainText)
    label.setWordWrap(True)
    policy = label.sizePolicy()  # Keep word-wrap's height-for-width flag.
    policy.setHorizontalPolicy(QSizePolicy.Ignored)
    label.setSizePolicy(policy)
    label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return label


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
        self.setWindowTitle("같은 보드 비교 — 알고리즘 결과")
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
        self.statistics = {HUMAN: human_statistics(context.human_replay)}
        for key, run in self.runs.items():
            self.statistics[key] = algorithm_statistics(board, run)
        self.row_keys = (HUMAN, *self.runs)

        layout = QVBoxLayout(self)
        selection = QHBoxLayout()
        selection.addWidget(QLabel("표시할 결과:"))
        self.shown_selector = QComboBox()
        self.shown_selector.setAccessibleName("Shown result")
        self.shown_selector.addItem("Human", HUMAN)
        for key in self.runs:
            if key in self.players:
                self.shown_selector.addItem(LABELS[key], key)
        self.shown_selector.currentIndexChanged.connect(self.on_shown_changed)
        selection.addWidget(self.shown_selector)
        self.status_label = _text_label()
        selection.addWidget(self.status_label, 1)
        self.legacy_button = QPushButton("Stage 2 / Stage 3 상세 창 열기")
        self.legacy_button.setVisible(execution is not None)
        self.legacy_button.clicked.connect(self.legacy_requested.emit)
        selection.addWidget(self.legacy_button)
        layout.addLayout(selection)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_summary(), "요약")
        self.tabs.addTab(self._build_board(board), "보드")
        self.tabs.addTab(self._build_statistics(), "통계")
        layout.addWidget(self.tabs, 1)

        controls = QHBoxLayout()
        for name, text, handler in (("first_button", "처음", lambda: self._seek(0)),
                                    ("previous_button", "이전", lambda: self._seek(self._index() - 1)),
                                    ("next_button", "다음", lambda: self._seek(self._index() + 1)),
                                    ("last_button", "마지막", lambda: self._seek(self._player().count))):
            button = QPushButton(text)
            button.clicked.connect(handler)
            setattr(self, name, button)
            controls.addWidget(button)
        self.slider = _IndexSlider(Qt.Horizontal)
        self.slider.setAccessibleName("Shown result action index")
        self.slider.valueChanged.connect(self._seek)
        self.slider.track_seek.connect(self._seek)
        controls.addWidget(self.slider, 1)
        self.index_label = QLabel()
        controls.addWidget(self.index_label)
        layout.addLayout(controls)

        playback = QHBoxLayout()
        self.play_button = QPushButton("재생")
        self.play_button.clicked.connect(self.on_play_pause)
        playback.addWidget(self.play_button)
        playback.addWidget(QLabel("간격:"))
        self.interval_entry = _IndexInterval()
        self.interval_entry.setRange(INDEX_INTERVAL_MIN_MS, INDEX_INTERVAL_MAX_MS)
        self.interval_entry.setValue(INDEX_INTERVAL_DEFAULT_MS)
        self.interval_entry.setSuffix(" ms")
        self.interval_entry.setSpecialValueText(f"최대 ({INDEX_INTERVAL_MIN_MS} ms)")
        self.interval_entry.setKeyboardTracking(False)
        self.interval_entry.setAccessibleName("Index autoplay interval")
        self.interval_entry.setToolTip("자동 재생에서 행동 1개를 보여 주는 간격입니다.")
        self.interval_entry.fit_text_width()
        self.interval_entry.valueChanged.connect(self.on_interval_changed)
        playback.addWidget(self.interval_entry)
        self.answer_checkbox = QCheckBox("숨은 정답 보기")
        self.answer_checkbox.setToolTip(ANSWER_TOOLTIP)
        self.answer_checkbox.toggled.connect(self._update_answers)
        playback.addWidget(self.answer_checkbox)
        playback.addStretch()
        layout.addLayout(playback)

        self.autoplay_timer = QTimer(self)
        self.autoplay_timer.timeout.connect(self._on_autoplay_tick)
        self.refresh()
        self.table.setCurrentCell(0, 0)
        available = self.screen().availableGeometry()
        self.resize(min(1200, available.width(), max(760, board.width * CELL_SIZE + 60)),
                    min(760, available.height()))

    # --- construction ---------------------------------------------------------

    def _build_summary(self):
        page = QWidget()
        column = QVBoxLayout(page)
        self.note_label = _text_label(RANKING_NOTE)
        column.addWidget(self.note_label)
        self.table = QTableWidget(len(self.row_keys), len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self._fill_table()
        self.table.currentCellChanged.connect(lambda row, *_: self._update_detail(row))
        column.addWidget(self.table, 1)
        self.detail_label = _text_label()
        column.addWidget(self.detail_label)
        return page

    def _build_board(self, board):
        self.board_container = QWidget()
        grid = QGridLayout(self.board_container)
        grid.setSpacing(0)
        grid.setContentsMargins(0, 0, 0, 0)
        self.cells = {}
        for y in range(board.height):
            for x in range(board.width):
                cell = _ComparisonCell(x, y, self.board_container)
                self.cells[x, y] = cell
                grid.addWidget(cell, y, x)
        self.board_container.setFixedSize(board.width * CELL_SIZE, board.height * CELL_SIZE)
        answers = derive_answer_clues(board.width, board.height, board.mine_positions)
        self.answer_overlay = _AnswerOverlay(self.board_container, answers, self.cells[0, 0].font())
        self.answer_overlay.setGeometry(self.board_container.rect())
        self.answer_overlay.raise_()
        self.answer_overlay.hide()
        scroll = QScrollArea()
        scroll.setWidget(self.board_container)
        scroll.setWidgetResizable(False)
        scroll.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        scroll.setMinimumSize(100, 100)
        return scroll

    def _build_statistics(self):
        page = QWidget()
        column = QVBoxLayout(page)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        captions = ["Human", *(LABELS[key] for key in self.runs)]
        self.statistics_headers = []
        for index, caption in enumerate(captions, 1):
            header = QLabel(caption)
            header.setWordWrap(True)
            header.setAlignment(Qt.AlignRight | Qt.AlignBottom)
            self.statistics_headers.append(header)
            grid.addWidget(header, 0, index)
            grid.setColumnStretch(index, 1)
        outcomes = (self.context.terminal_status.name, *(run.outcome for run in self.runs.values()))
        rows = [("결과", outcomes)]
        rows += [(caption, tuple(self.statistics[key][stat] for key in self.row_keys))
                 for stat, caption in STAT_LABELS]
        self.statistics_labels = {}
        for row, (caption, values) in enumerate(rows, 1):
            grid.addWidget(QLabel(caption), row, 0)
            labels = []
            for index, value in enumerate(values, 1):
                label = QLabel(value)
                label.setTextFormat(Qt.PlainText)
                label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                label.setTextInteractionFlags(Qt.TextSelectableByMouse)
                grid.addWidget(label, row, index)
                labels.append(label)
            self.statistics_labels[caption] = tuple(labels)
        column.addLayout(grid)
        self.statistics_note = _text_label(STATISTICS_NOTE)
        column.addWidget(self.statistics_note)
        column.addStretch()
        self.statistics_scroll = QScrollArea()
        self.statistics_scroll.setWidgetResizable(True)
        self.statistics_scroll.setWidget(page)
        return self.statistics_scroll

    def _fill_table(self):
        human = self.statistics[HUMAN]
        rows = [("Human", self.context.terminal_status.name, human["bbbv"],
                 len(self.context.human_replay.events), human["efficiency"], human["ioe"], "—")]
        for key, run in self.runs.items():
            stats = self.statistics[key]
            model = "—" if run.model_c_total_us is None else f"{run.model_c_total_us / 1e6:.3f}"
            actions = "—" if run.actions is None else run.actions.semantic_action_count
            rows.append((run.label, run.outcome, stats["bbbv"], actions, stats["efficiency"], stats["ioe"], model))
        for row, values in enumerate(rows):
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)

    def detail_text(self, key):
        if key == HUMAN:
            outcome = self.context.terminal_status.name
            return (f"선택한 결과: Human\n최종 결과: {outcome} ({OUTCOME_NAMES.get(outcome, outcome)})\n"
                    f"설명: {HUMAN_DETAIL}")
        run = self.runs[key]
        lines = [f"선택한 결과: {run.label}",
                 f"최종 결과: {run.outcome} ({OUTCOME_NAMES[run.outcome]})", "설정:"]
        lines += [f"  · {name}: {value}" for name, value in run.settings] or ["  · (기록 없음)"]
        if run.detail:
            lines.append(f"설명: {run.detail}")
        if run.time_dependent:
            lines.append(TIME_DEPENDENCE_NOTE)
        return "\n".join(lines)

    def _update_detail(self, row):
        if self._closed or not 0 <= row < len(self.row_keys):
            return
        self.detail_label.setText(self.detail_text(self.row_keys[row]))

    # --- navigation -----------------------------------------------------------

    def shown_key(self):
        return self.shown_selector.currentData()

    def _player(self):
        return self.players[self.shown_key()]

    def _index(self):
        return self.positions[self.shown_key()]

    def _seek(self, index):
        """Every manual move (buttons, slider track or drag) stops autoplay first."""
        if self._closed:
            return
        self.autoplay_timer.stop()
        self._apply(index)

    def _apply(self, index):
        player = self._player()
        index = max(0, min(player.count, int(index)))
        if player.index != index:
            player.go_to(index)
        self.positions[self.shown_key()] = index
        self.refresh()

    def on_shown_changed(self, _index):
        if self._closed:
            return
        self.autoplay_timer.stop()
        player = self._player()
        if player.index != self._index():
            player.go_to(self._index())
        self.table.setCurrentCell(self.row_keys.index(self.shown_key()), 0)
        self.refresh()

    # --- autoplay ------------------------------------------------------------

    def on_play_pause(self):
        if self._closed:
            return
        if self.autoplay_timer.isActive():
            self.autoplay_timer.stop()
        elif self._index() < self._player().count:
            self.autoplay_timer.start(self.interval_entry.value())
        self._sync_play_button()

    def _on_autoplay_tick(self):
        if self._closed or not self.autoplay_timer.isActive():
            return
        self._apply(self._index() + 1)
        if self._index() >= self._player().count:
            self.autoplay_timer.stop()  # Stops at the end, like the existing window.
            self._sync_play_button()

    def on_interval_changed(self, value):
        if not self._closed and self.autoplay_timer.isActive():
            self.autoplay_timer.setInterval(value)  # Keeps playing at the new interval.

    def _sync_play_button(self):
        running = self.autoplay_timer.isActive()
        self.play_button.setText("일시정지" if running else "재생")
        self.play_button.setEnabled(running or self._index() < self._player().count)

    def _update_answers(self, _checked=None):
        if self._closed:
            return
        self.answer_overlay.setVisible(self.answer_checkbox.isChecked())
        self.answer_overlay.update()

    def refresh(self):
        if self._closed:
            return
        player, index = self._player(), self._index()
        observation = player.observation()
        for y, row in enumerate(observation):
            for x, value in enumerate(row):
                self.cells[x, y].render_state(value)
        self.answer_overlay.hidden_mask = tuple(tuple(value == CellState.HIDDEN for value in row)
                                                for row in observation)
        self._update_answers()
        key, status = self.shown_key(), player.status()
        board = f"현재 보드: {BOARD_STATUS_NAMES.get(status, status)} ({status})"
        final = "기록된 Human 판" if key == HUMAN else f"최종 결과: {self.runs[key].outcome}"
        self.status_label.setText(f"{LABELS.get(key, 'Human')} — {board}, {final}")
        self.index_label.setText(f"행동 {index} / {player.count}")
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
        self._sync_play_button()

    def closeEvent(self, event):
        super().closeEvent(event)
        if event.isAccepted() and not self._closed:
            self._closed = True
            self.autoplay_timer.stop()
            self.closed.emit()
