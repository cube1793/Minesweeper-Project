"""
ui_manager.py
PyQt5 기반 지뢰찾기 화면 및 인터페이스.

core_engine.MinesweeperEngine 를 의존성 주입받아 구동된다.
UI는 게임 상태를 독립적으로 계산하지 않으며,
오직 engine.get_observation() 결과만으로 보드를 렌더링한다.
통계 또한 엔진이 산출한 stats 딕셔너리를 받아 '표시'만 한다.

레이아웃 전략:
    - 최상위 레이아웃은 QHBoxLayout(좌우 분할)이다.
        * [왼쪽] 통계 사이드 패널(Counters): 클래식 Arbiter 스타일의
          2열(항목명 | 값) QTableWidget. FixedWidth로 폭을 제한하고
          테두리/배경으로 보드 영역과 시각적으로 분리한다.
        * [오른쪽] 기존 게임 영역: 설정 바 + 정보 바(리셋/타이머) +
          보드 스크롤 영역(QScrollArea).
    - 셀은 사용자가 지정한 고정 px 정사각형(QSpinBox로 조절, 10~60px).
    - 그리드는 spacing=0, margins=0 으로 클래식하게 촘촘히 붙인다.
    - 보드는 별도 컨테이너 위젯에 담아 QScrollArea로 감싼다.

통계 패널 연동 전략:
    - 값 셀(QTableWidgetItem)을 키(stat key)로 보관해두고
      _update_statistics_panel(stats_dict) 메서드로 일괄 갱신한다.
    - 엔진이 상태별 마스킹/포맷(예: PLAYING 중 "-/-", 종료 시 "X + Y")을
      모두 적용해 던지므로 UI는 받은 문자열을 그대로 표시한다.

[클릭 분석 패널 확장]:
    - 'Clicks' 항목 바로 아래에 'Left', 'Right', 'Chord' 3개 행을 추가한다.
    - 테이블 순서: ... 3BV/s, Clicks, Left, Right, Chord, CPS, Efficiency, IOE ...
    - 진행 중에는 각 항목이 (Active+Wasted) 합산 정수, 종료 시 "X + Y"
      (초과가 0이면 "X"만)로 엔진에서 포맷되어 들어온다.

테두리 단계 규칙 (셀 크기에 따른 고정 정수 px):
    - 20px 미만   : 1px solid #ffffff (플랫, 밝은 톤 유지)
    - 20px~45px   : 2px outset #ffffff (클래식 입체감 표준)
    - 45px 초과   : 3px outset #ffffff (대형 셀 입체감 유지)
"""

from enum import IntEnum

from PyQt5.QtWidgets import (
    QWidget, QPushButton, QGridLayout, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QSizePolicy, QShortcut, QInputDialog,
    QSpinBox, QScrollArea, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QHeaderView, QFileDialog, QMessageBox,
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QKeySequence, QColor

from core_engine import MinesweeperEngine, CellState, GameStatus, Action
from replay_json import load_replay_json, save_replay_json
from replay_player import ReplayPlayer
from replay_recorder import ReplayRecorder


# 타일 숫자별 클래식/Arbiter 스타일 색상
NUMBER_COLORS = {
    1: "#0000FF",  # 파랑
    2: "#008000",  # 초록
    3: "#FF0000",  # 빨강
    4: "#000080",  # 남색
    5: "#800000",  # 적갈
    6: "#008080",  # 청록
    7: "#000000",  # 검정
    8: "#808080",  # 회색
}

MIN_CELL_SIZE = 10
MAX_CELL_SIZE = 60
DEFAULT_CELL_SIZE = 28
MAX_DIMENSION = 100  # 커스텀 가로/세로 최대 칸 수

# 통계 패널 폭(px). 150~180 권장 범위 내.
REPLAY_AUTOPLAY_INTERVAL_MS = 200
STATS_PANEL_WIDTH = 170


class ChordMode(IntEnum):
    """화음 작동 방식 옵션 (UI 정책)."""
    LEFT_CLICK = 0   # 모드 A: 좌클릭 또는 동시 좌우클릭으로 발동
    BOTH_CLICK = 1   # 모드 B: 동시 좌우클릭으로만 발동
    DISABLED = 2     # 모드 C: 화음 비활성화


# 난이도 프리셋: 표시이름 -> (width, height, mines)
DIFFICULTY_PRESETS = {
    "초급 (9x9, 10)": (9, 9, 10),
    "중급 (16x16, 40)": (16, 16, 40),
    "상급 (30x16, 99)": (30, 16, 99),
    "커스텀": None,
}


# ----------------------------------------------------------------------
# 통계 패널 항목 정의
#   (stat_key, 표시 라벨, 초기/더미 표시값)
#   - stat_key 는 _update_statistics_panel(stats_dict) 연동 키.
#   - 화면 표시는 위에서 아래로 이 순서를 그대로 따른다.
#   - 'Clicks' 바로 아래에 클릭 분석 세부 항목(Left/Right/Chord)을 배치한다.
# ----------------------------------------------------------------------
STAT_ROWS = [
    ("time",            "Time",           "0.00 (0)"),
    ("est_time",        "Est Time",       "999.99 (999)"),
    ("bbbv",            "3BV",            "0/0"),
    ("bbbv_per_sec",    "3BV/s",          "0"),
    ("clicks",          "Clicks",         "0"),
    ("left",            "Left",           "0"),
    ("right",           "Right",          "0"),
    ("chord",           "Chord",          "0"),
    ("cps",             "CPS",            "0"),
    ("efficiency",      "Efficiency",     "0%"),
    ("ioe",             "IOE",            "0"),
    ("ops",             "Ops",            "0/0"),
    ("thrp",            "ThrP",           "0"),
    ("corr",            "Corr",           "0"),
    ("zini",            "ZiNi",           "0"),
    ("zne",             "ZNE",            "0"),
    ("znt",             "ZNT",            "0"),
    ("rqp",             "RQP",            "0"),
    ("ios",             "IOS",            "0"),
]


def border_width_for(cell_size: int) -> int:
    """셀 크기에 따른 고정 테두리 두께(px)를 단계별로 반환한다."""
    if cell_size < 20:
        return 1
    elif cell_size <= 45:
        return 2
    else:
        return 3


class CellButton(QPushButton):
    """
    좌/우클릭 및 동시 좌우클릭 시그널을 방출하는 커스텀 버튼.
    동시 클릭(both)은 한쪽 버튼이 눌린 상태에서 다른 쪽이 눌릴 때 감지한다.
    """
    left_clicked = pyqtSignal(int, int)
    right_clicked = pyqtSignal(int, int)
    both_clicked = pyqtSignal(int, int)

    def __init__(self, x: int, y: int, parent=None):
        super().__init__(parent)
        self.x = x
        self.y = y
        self.setFocusPolicy(Qt.NoFocus)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def mousePressEvent(self, event):
        buttons = event.buttons()
        if buttons == (Qt.LeftButton | Qt.RightButton):
            self.both_clicked.emit(self.x, self.y)
        elif event.button() == Qt.LeftButton:
            self.left_clicked.emit(self.x, self.y)
        elif event.button() == Qt.RightButton:
            self.right_clicked.emit(self.x, self.y)


class MinesweeperUI(QWidget):
    """엔진을 주입받아 화면을 그리는 메인 위젯."""

    def __init__(self, engine: MinesweeperEngine):
        super().__init__()
        self.engine = engine
        self._game_over = False
        self._buttons = {}
        self._chord_mode = ChordMode.LEFT_CLICK
        self._cell_size = DEFAULT_CELL_SIZE
        self._replay_mode = False
        self._replay_player = None
        self._normal_game_config = (
            self.engine.width,
            self.engine.height,
            self.engine.num_mines,
        )
        self._replay_recorder = ReplayRecorder(
            width=self.engine.width,
            height=self.engine.height,
            num_mines=self.engine.num_mines,
        )

        # 통계 패널의 값 셀(QTableWidgetItem)을 stat_key로 보관.
        # _update_statistics_panel() 이 이 매핑을 통해 값을 갱신한다.
        self._replay_autoplay_timer = QTimer(self)
        self._replay_autoplay_timer.setInterval(REPLAY_AUTOPLAY_INTERVAL_MS)
        self._replay_autoplay_timer.timeout.connect(self._advance_replay_autoplay)
        self._stat_value_items = {}

        self._elapsed_seconds = 0
        self._timer = QTimer(self)
        # 고주파(10ms) 폴링: 왼쪽 패널 Time의 소수점 한 자리가 매끄럽게
        # 흐르도록 한다. 시간 측정 자체는 엔진의 perf_counter가 담당하고,
        # UI는 engine.get_elapsed_time()을 폴링해 표시만 한다.
        self._timer.setInterval(10)
        self._timer.timeout.connect(self._on_timer_tick)
        self._timer_running = False

        self._init_ui()
        self._init_shortcuts()
        self.render_board()
        # 시작 시 PLAYING 상태 → 3BV/Ops는 마스킹("-/-"), 클릭류는 "0"
        self._update_statistics_panel(self.engine.get_stats())

    # ------------------------------------------------------------------
    # UI 구성
    # ------------------------------------------------------------------
    def _init_ui(self):
        self.setWindowTitle("지뢰찾기")

        # 최상위: 좌우 분할
        root_layout = QHBoxLayout()
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(8)

        # [왼쪽] 통계 사이드 패널
        self.stats_panel = self._build_stats_panel()
        root_layout.addWidget(self.stats_panel)

        # [오른쪽] 기존 게임 영역(설정 바 + 정보 바 + 보드)
        right_panel = self._build_game_area()
        root_layout.addLayout(right_panel)

        self.setLayout(root_layout)

        self._build_grid()
        self._update_timer_label()
        self._apply_initial_window_size()

    def _build_stats_panel(self) -> QWidget:
        """
        왼쪽 통계 사이드 패널을 구성한다.
        제목 라벨 + 2열(항목명 | 값) QTableWidget 형태로,
        클래식 Arbiter Counters의 외형을 재현한다.
        """
        panel = QWidget()
        panel.setFixedWidth(STATS_PANEL_WIDTH)
        panel.setObjectName("statsPanel")
        panel.setStyleSheet(
            "#statsPanel {"
            " background-color: #f0f0f0;"
            " border: 1px solid #808080;"
            "}"
        )

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # 패널 제목
        title = QLabel("Counters")
        title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        title.setStyleSheet("color: #202020; padding: 2px;")
        layout.addWidget(title)

        # 통계 테이블
        self.stats_table = self._build_stats_table()
        layout.addWidget(self.stats_table)

        return panel

    def _build_stats_table(self) -> QTableWidget:
        """
        2열 통계 테이블을 만들고, 값 셀 참조를 _stat_value_items에 저장한다.
        - 헤더/그리드선을 정리해 촘촘한 Counters 룩을 만든다.
        - 사용자가 편집/선택하지 못하도록 읽기 전용으로 설정한다.
        - Left/Right/Chord 등 세부 항목도 동일한 방식으로 행을 만든다.
        """
        table = QTableWidget(len(STAT_ROWS), 2)
        table.setObjectName("statsTable")

        # 헤더/스크롤/선택 동작 정리
        table.horizontalHeader().setVisible(False)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(True)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setFocusPolicy(Qt.NoFocus)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # 열 너비: 0열(항목명)은 고정, 1열(값)은 나머지 공간 신축
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        table.setColumnWidth(0, 72)

        label_font = QFont("Segoe UI", 8)
        value_font = QFont("Consolas", 8)

        for row, (key, label, dummy) in enumerate(STAT_ROWS):
            # 0열: 항목명
            name_item = QTableWidgetItem(label)
            name_item.setFont(label_font)
            name_item.setFlags(Qt.ItemIsEnabled)
            name_item.setForeground(QColor("#303030"))
            table.setItem(row, 0, name_item)

            # 1열: 값(더미). stat_key로 참조 보관.
            value_item = QTableWidgetItem(dummy)
            value_item.setFont(value_font)
            value_item.setFlags(Qt.ItemIsEnabled)
            value_item.setForeground(QColor("#000080"))
            table.setItem(row, 1, value_item)

            self._stat_value_items[key] = value_item

            # 행 높이를 촘촘하게
            table.setRowHeight(row, 20)

        table.setStyleSheet(
            "#statsTable {"
            " background-color: #ffffff;"
            " border: 1px solid #a0a0a0;"
            " gridline-color: #d0d0d0;"
            "}"
            "QTableWidget::item { padding-left: 3px; }"
        )
        return table

    def _build_game_area(self) -> QVBoxLayout:
        """
        오른쪽 게임 영역을 구성한다.
        설정 바 + 정보 바(리셋/타이머) + 보드 스크롤 영역을
        세로로 쌓는 기존 레이아웃을 그대로 유지한다.
        """
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # --- 설정 바: 난이도 + 화음 모드 + 셀 크기 ---
        settings_bar = QHBoxLayout()

        settings_bar.addWidget(QLabel("난이도:"))
        self.difficulty_combo = QComboBox()
        self.difficulty_combo.addItems(DIFFICULTY_PRESETS.keys())
        self.difficulty_combo.setCurrentText("상급 (30x16, 99)")
        self.difficulty_combo.currentTextChanged.connect(self.on_difficulty_changed)
        self.difficulty_combo.setFocusPolicy(Qt.NoFocus)
        settings_bar.addWidget(self.difficulty_combo)

        settings_bar.addSpacing(12)
        settings_bar.addWidget(QLabel("화음:"))
        self.chord_combo = QComboBox()
        self.chord_combo.addItems([
            "모드 A (좌클릭)",
            "모드 B (좌우클릭)",
            "모드 C (비활성화)",
        ])
        self.chord_combo.currentIndexChanged.connect(self.on_chord_mode_changed)
        self.chord_combo.setFocusPolicy(Qt.NoFocus)
        settings_bar.addWidget(self.chord_combo)

        settings_bar.addSpacing(12)
        settings_bar.addWidget(QLabel("셀 크기:"))
        self.cell_size_spin = QSpinBox()
        self.cell_size_spin.setRange(MIN_CELL_SIZE, MAX_CELL_SIZE)
        self.cell_size_spin.setValue(DEFAULT_CELL_SIZE)
        self.cell_size_spin.setSuffix(" px")
        self.cell_size_spin.setFocusPolicy(Qt.ClickFocus)
        self.cell_size_spin.valueChanged.connect(self.on_cell_size_changed)
        settings_bar.addWidget(self.cell_size_spin)

        settings_bar.addStretch()
        main_layout.addLayout(settings_bar)

        # --- 상단 정보 바: 지뢰 카운터 + 리셋 + 타이머 ---
        top_bar = QHBoxLayout()
        self.mine_label = QLabel()
        self.mine_label.setFont(QFont("Consolas", 12, QFont.Bold))

        self.reset_button = QPushButton("🙂")
        self.reset_button.setFixedSize(36, 36)
        self.reset_button.setFont(QFont("Arial", 14))
        self.reset_button.setFocusPolicy(Qt.NoFocus)
        self.reset_button.clicked.connect(self.on_reset)

        self.timer_label = QLabel()
        self.timer_label.setFont(QFont("Consolas", 12, QFont.Bold))

        self.save_replay_button = QPushButton("Replay 저장")
        self.save_replay_button.setFocusPolicy(Qt.NoFocus)
        self.save_replay_button.clicked.connect(self.on_save_replay)

        self.load_replay_button = QPushButton("Replay 불러오기")
        self.load_replay_button.setFocusPolicy(Qt.NoFocus)
        self.load_replay_button.clicked.connect(self.on_load_replay)

        self.replay_status_label = QLabel()
        self.replay_status_label.setFont(QFont("Consolas", 10, QFont.Bold))
        self.replay_status_label.setVisible(False)

        self.replay_play_button = QPushButton("재생")
        self.replay_play_button.setFocusPolicy(Qt.NoFocus)
        self.replay_play_button.clicked.connect(self.on_replay_play_pause)
        self.replay_play_button.setVisible(False)

        self.replay_first_button = QPushButton("처음")
        self.replay_first_button.setFocusPolicy(Qt.NoFocus)
        self.replay_first_button.clicked.connect(self.on_replay_first)
        self.replay_first_button.setVisible(False)

        self.replay_prev_button = QPushButton("이전")
        self.replay_prev_button.setFocusPolicy(Qt.NoFocus)
        self.replay_prev_button.clicked.connect(self.on_replay_previous)
        self.replay_prev_button.setVisible(False)

        self.replay_next_button = QPushButton("다음")
        self.replay_next_button.setFocusPolicy(Qt.NoFocus)
        self.replay_next_button.clicked.connect(self.on_replay_next)
        self.replay_next_button.setVisible(False)

        self.replay_last_button = QPushButton("끝")
        self.replay_last_button.setFocusPolicy(Qt.NoFocus)
        self.replay_last_button.clicked.connect(self.on_replay_last)
        self.replay_last_button.setVisible(False)

        self.exit_replay_button = QPushButton("Replay 종료")
        self.exit_replay_button.setFocusPolicy(Qt.NoFocus)
        self.exit_replay_button.clicked.connect(self.on_exit_replay)
        self.exit_replay_button.setVisible(False)

        top_bar.addWidget(self.mine_label)
        top_bar.addStretch()
        top_bar.addWidget(self.reset_button)
        top_bar.addStretch()
        top_bar.addWidget(self.timer_label)
        top_bar.addSpacing(12)
        top_bar.addWidget(self.save_replay_button)
        top_bar.addWidget(self.load_replay_button)
        top_bar.addSpacing(12)
        top_bar.addWidget(self.replay_play_button)
        top_bar.addWidget(self.replay_first_button)
        top_bar.addWidget(self.replay_prev_button)
        top_bar.addWidget(self.replay_next_button)
        top_bar.addWidget(self.replay_last_button)
        top_bar.addWidget(self.replay_status_label)
        top_bar.addWidget(self.exit_replay_button)
        main_layout.addLayout(top_bar)

        # --- 보드: 컨테이너 위젯 + 그리드, QScrollArea로 감싸기 ---
        self.board_container = QWidget()
        self.grid = QGridLayout(self.board_container)
        self.grid.setSpacing(0)
        self.grid.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.board_container)
        self.scroll_area.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.scroll_area.setWidgetResizable(False)
        main_layout.addWidget(self.scroll_area)

        return main_layout

    def _build_grid(self):
        """엔진 크기에 맞춰 그리드 버튼을 (재)생성한다."""
        for btn in self._buttons.values():
            self.grid.removeWidget(btn)
            btn.deleteLater()
        self._buttons.clear()

        for y in range(self.engine.height):
            for x in range(self.engine.width):
                btn = CellButton(x, y)
                btn.setFixedSize(self._cell_size, self._cell_size)
                btn.left_clicked.connect(self.on_left_click)
                btn.right_clicked.connect(self.on_right_click)
                btn.both_clicked.connect(self.on_both_click)
                self.grid.addWidget(btn, y, x)
                self._buttons[(x, y)] = btn

        self._resize_board_container()

    def _resize_board_container(self):
        """보드 컨테이너를 셀 크기 x 칸 수에 딱 맞게 고정."""
        w = self.engine.width * self._cell_size
        h = self.engine.height * self._cell_size
        self.board_container.setFixedSize(w, h)

    def _apply_initial_window_size(self):
        """초기 창 크기를 보드 비율에 맞춰 설정(화면 초과 시 적당히 제한)."""
        board_w = self.engine.width * self._cell_size
        board_h = self.engine.height * self._cell_size
        # 왼쪽 통계 패널 폭 + 여백을 추가로 고려한다.
        w = min(board_w + STATS_PANEL_WIDTH + 60, 1500)
        h = min(board_h + 130, 900)
        self.resize(w, h)

    def _init_shortcuts(self):
        """창 전체에 글로벌 작동하는 재시작 단축키."""
        for key in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            sc = QShortcut(QKeySequence(key), self)
            sc.setContext(Qt.WindowShortcut)
            sc.activated.connect(self.on_reset)

    # ------------------------------------------------------------------
    # 타이머 처리
    #   - 시간 측정의 '진실 공급원'은 엔진(perf_counter)이다.
    #   - UI 타이머는 10ms마다 깨어나 engine.get_elapsed_time()을 폴링하여
    #     (1) 오른쪽 상단 정수 타이머(timer_label)와
    #     (2) 왼쪽 통계 패널의 소수점 Time 항목을 동시에 갱신한다.
    # ------------------------------------------------------------------
    def _start_timer(self):
        if not self._timer_running:
            self._timer_running = True
            self._timer.start()

    def _stop_timer(self):
        self._timer_running = False
        self._timer.stop()

    def _reset_timer(self):
        self._stop_timer()
        self._elapsed_seconds = 0
        self._update_timer_label()

    def _on_timer_tick(self):
        """
        10ms 주기 폴링 핸들러.
        엔진의 실시간 경과 시간으로 오른쪽 정수 타이머와
        왼쪽 패널의 소수점 Time을 함께 갱신한다.
        """
        elapsed = self.engine.get_elapsed_time()
        self._elapsed_seconds = int(elapsed)
        self._update_timer_label()
        # 진행 중 Time 항목(소수 한 자리)을 실시간으로 갱신.
        # get_stats()는 PLAYING이면 time만 .1f로 채우고 나머지는 마스킹한다.
        if self.engine.status == GameStatus.PLAYING:
            self._update_statistics_panel({"time": f"{elapsed:.1f}"})

    def _update_timer_label(self):
        """
        오른쪽 상단 정보 바의 타이머: 왼쪽 패널 소수점과 무관하게
        '정수 초'를 3자리로만 표시한다(클래식 규칙 유지).
        """
        display = min(self._elapsed_seconds, 999)
        self.timer_label.setText(f"⏱ {display:03d}")

    # ------------------------------------------------------------------
    # 통계 패널 갱신 인터페이스
    # ------------------------------------------------------------------
    def _update_statistics_panel(self, stats_dict: dict):
        """
        통계 패널의 값들을 일괄 갱신한다.

        Args:
            stats_dict: { stat_key: 표시문자열 또는 값 } 형태의 딕셔너리.
                        STAT_ROWS에 정의된 키만 반영되며, 정의되지 않은
                        키는 조용히 무시한다. 누락된 키는 기존 값을 유지한다.

        주의:
            엔진이 상태별 마스킹/포맷(예: PLAYING 중 "-/-", 종료 시
            "X + Y" 또는 "X")을 모두 적용해 넘겨주므로, UI는 받은 값을
            문자열로 그대로 표시하기만 한다(표시 책임만 수행).
            time/est_time/bbbv/bbbv_per_sec/clicks/left/right/chord/cps 등
            엔진이 채워주는 키는 자동으로 해당 행에 반영된다.
        """
        for key, value in stats_dict.items():
            item = self._stat_value_items.get(key)
            if item is not None:
                item.setText(str(value))

    # ------------------------------------------------------------------
    # 리플레이 기록/저장
    # ------------------------------------------------------------------
    def _reset_replay_recorder(self):
        """현재 엔진 설정 기준으로 한 판 리플레이 기록을 초기화한다."""
        self._replay_recorder.reset(
            width=self.engine.width,
            height=self.engine.height,
            num_mines=self.engine.num_mines,
        )

    def _record_replay_event(self, x: int, y: int, action: Action):
        """engine.step()으로 실제 처리된 클릭 이벤트를 recorder에 반영한다."""
        try:
            self._replay_recorder.record_event(
                elapsed_time=self.engine.get_elapsed_time(),
                x=x,
                y=y,
                action=action,
            )
            self._capture_replay_board_if_ready()
        except Exception as exc:
            # 리플레이 기록 실패가 기존 게임 플레이를 중단시키지 않도록 한다.
            print(f"[Replay warning] 이벤트 기록 실패: {exc}")

    def _capture_replay_board_if_ready(self):
        """지뢰 배치가 확정된 뒤 한 번만 보드 정보를 recorder에 저장한다."""
        if self._replay_recorder.board is not None:
            return

        snapshot = self.engine.get_board_snapshot()
        if snapshot.mines_placed:
            self._replay_recorder.capture_board(snapshot)

    def on_save_replay(self):
        """현재 판 리플레이를 JSON 파일로 저장한다."""
        if self._replay_mode:
            QMessageBox.information(
                self,
                "리플레이 저장",
                "리플레이 모드에서는 저장할 수 없습니다.",
            )
            return

        self._capture_replay_board_if_ready()

        try:
            replay_data = self._replay_recorder.to_replay_data()
        except ValueError:
            QMessageBox.information(
                self,
                "리플레이 저장",
                "지뢰가 아직 배치되지 않아 저장할 리플레이가 없습니다.",
            )
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "리플레이 저장",
            "replay.json",
            "Replay JSON (*.json);;All Files (*)",
        )
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"

        try:
            save_replay_json(replay_data, path)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "리플레이 저장 실패",
                f"리플레이를 저장하지 못했습니다.\n{exc}",
            )
            return

        QMessageBox.information(
            self,
            "리플레이 저장",
            "리플레이를 저장했습니다.",
        )

    def on_load_replay(self):
        """JSON 리플레이 파일을 불러와 리플레이 모드로 진입한다."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "리플레이 불러오기",
            "",
            "Replay JSON (*.json);;All Files (*)",
        )
        if not path:
            return

        try:
            replay_data = load_replay_json(path)
            replay_player = ReplayPlayer(replay_data)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "리플레이 불러오기 실패",
                f"리플레이를 불러오지 못했습니다.\n{exc}",
            )
            return

        self._enter_replay_mode(replay_player)

    def on_exit_replay(self):
        """리플레이 모드를 끝내고 현재 선택된 난이도로 새 일반 게임을 시작한다."""
        self._exit_replay_mode()

    def on_replay_play_pause(self):
        if not self._replay_mode or self._replay_player is None:
            return

        if self._replay_player.current_index >= self._replay_player.event_count:
            self._stop_replay_autoplay()
            self._update_replay_controls()
            return

        if self._replay_autoplay_timer.isActive():
            self._stop_replay_autoplay()
        else:
            self.replay_play_button.setText("일시정지")
            self._replay_autoplay_timer.start()

    def _advance_replay_autoplay(self):
        if not self._replay_mode or self._replay_player is None:
            self._stop_replay_autoplay()
            return

        if self._replay_player.current_index >= self._replay_player.event_count:
            self._stop_replay_autoplay()
            self._update_replay_controls()
            return

        self._replay_player.next()
        self._refresh_replay_view_after_move()

        if self._replay_player.current_index >= self._replay_player.event_count:
            self._stop_replay_autoplay()
            self._update_replay_controls()

    def _stop_replay_autoplay(self):
        if self._replay_autoplay_timer.isActive():
            self._replay_autoplay_timer.stop()
        self.replay_play_button.setText("재생")

    def on_replay_first(self):
        if not self._replay_mode or self._replay_player is None:
            return
        self._stop_replay_autoplay()
        self._replay_player.go_to(0)
        self._refresh_replay_view_after_move()

    def on_replay_previous(self):
        if not self._replay_mode or self._replay_player is None:
            return
        self._stop_replay_autoplay()
        self._replay_player.previous()
        self._refresh_replay_view_after_move()

    def on_replay_next(self):
        if not self._replay_mode or self._replay_player is None:
            return
        self._stop_replay_autoplay()
        self._replay_player.next()
        self._refresh_replay_view_after_move()

    def on_replay_last(self):
        if not self._replay_mode or self._replay_player is None:
            return
        self._stop_replay_autoplay()
        self._replay_player.go_to(self._replay_player.event_count)
        self._refresh_replay_view_after_move()

    def _refresh_replay_view_after_move(self):
        if self._replay_player is None:
            return
        self.engine = self._replay_player.engine
        self.render_board()
        self._update_replay_status_label()
        self._update_replay_controls()

    def _enter_replay_mode(self, replay_player: ReplayPlayer):
        """ReplayPlayer의 초기 상태를 UI에 표시한다."""
        self._normal_game_config = (
            self.engine.width,
            self.engine.height,
            self.engine.num_mines,
        )
        self._replay_mode = True
        self._replay_player = replay_player
        self.engine = replay_player.engine
        self._game_over = False
        self.reset_button.setText("🙂")
        self._reset_timer()

        self._build_grid()
        self._apply_initial_window_size()
        self.render_board()
        self._update_statistics_panel(self.engine.get_stats())
        self._update_replay_status_label()
        self._update_replay_controls()

    def _exit_replay_mode(self):
        """일반 플레이 모드로 돌아가 현재 선택 난이도로 새 게임을 시작한다."""
        self._stop_replay_autoplay()
        self._replay_mode = False
        self._replay_player = None
        self._update_replay_controls()

        width, height, mines = self._normal_game_config
        self.engine.width = width
        self.engine.height = height
        self.engine.num_mines = mines
        self.engine.reset()
        self._game_over = False
        self.reset_button.setText("🙂")
        self._reset_timer()
        self._reset_replay_recorder()
        self._build_grid()
        self._apply_initial_window_size()
        self.render_board()
        self._update_statistics_panel(self.engine.get_stats())

    def _update_replay_status_label(self):
        """현재 리플레이 index/time을 표시한다."""
        if not self._replay_mode or self._replay_player is None:
            self.replay_status_label.setText("")
            return

        self.replay_status_label.setText(
            f"Replay {self._replay_player.current_index} / "
            f"{self._replay_player.event_count}   "
            f"{self._replay_player.current_time:.3f}s"
        )

    def _update_replay_controls(self):
        """일반/리플레이 모드에 맞춰 버튼 상태를 갱신한다."""
        in_replay = self._replay_mode and self._replay_player is not None
        at_start = in_replay and self._replay_player.current_index == 0
        at_end = (
            in_replay
            and self._replay_player.current_index == self._replay_player.event_count
        )

        self.reset_button.setEnabled(not self._replay_mode)
        self.save_replay_button.setEnabled(not self._replay_mode)
        self.load_replay_button.setEnabled(not self._replay_mode)
        self.difficulty_combo.setEnabled(not self._replay_mode)
        self.chord_combo.setEnabled(not self._replay_mode)
        self.cell_size_spin.setEnabled(not self._replay_mode)
        self.replay_status_label.setVisible(self._replay_mode)
        self.replay_play_button.setVisible(in_replay)
        self.replay_play_button.setEnabled(in_replay and not at_end)
        self.replay_play_button.setText(
            "일시정지" if self._replay_autoplay_timer.isActive() else "재생"
        )
        self.replay_first_button.setVisible(in_replay)
        self.replay_prev_button.setVisible(in_replay)
        self.replay_next_button.setVisible(in_replay)
        self.replay_last_button.setVisible(in_replay)
        self.replay_first_button.setEnabled(in_replay and not at_start)
        self.replay_prev_button.setEnabled(in_replay and not at_start)
        self.replay_next_button.setEnabled(in_replay and not at_end)
        self.replay_last_button.setEnabled(in_replay and not at_end)
        self.exit_replay_button.setVisible(self._replay_mode)

    # ------------------------------------------------------------------
    # 설정 핸들러
    # ------------------------------------------------------------------
    def on_chord_mode_changed(self, index: int):
        self._chord_mode = ChordMode(index)

    def on_cell_size_changed(self, value: int):
        """셀 크기 변경 시 모든 버튼과 컨테이너를 갱신."""
        self._cell_size = value
        for btn in self._buttons.values():
            btn.setFixedSize(value, value)
        self._resize_board_container()
        self.render_board()

    def on_difficulty_changed(self, text: str):
        preset = DIFFICULTY_PRESETS.get(text)
        if preset is None:
            dims = self._ask_custom_dimensions()
            if dims is None:
                self.difficulty_combo.blockSignals(True)
                self.difficulty_combo.setCurrentText("상급 (30x16, 99)")
                self.difficulty_combo.blockSignals(False)
                preset = DIFFICULTY_PRESETS["상급 (30x16, 99)"]
            else:
                preset = dims

        width, height, mines = preset
        self._rebuild_game(width, height, mines)

    def _ask_custom_dimensions(self):
        """커스텀 난이도 입력 다이얼로그. (width, height, mines) 또는 None."""
        width, ok = QInputDialog.getInt(
            self, "커스텀 - 가로", "가로 칸 수 (1~100):", 30, 1, MAX_DIMENSION
        )
        if not ok:
            return None
        height, ok = QInputDialog.getInt(
            self, "커스텀 - 세로", "세로 칸 수 (1~100):", 16, 1, MAX_DIMENSION
        )
        if not ok:
            return None
        max_mines = width * height - 1
        mines, ok = QInputDialog.getInt(
            self, "커스텀 - 지뢰",
            f"지뢰 개수 (1~{max_mines}):", min(99, max_mines), 1, max_mines
        )
        if not ok:
            return None
        return (width, height, mines)

    def _rebuild_game(self, width: int, height: int, mines: int):
        """새 난이도로 엔진과 그리드를 재구성한다."""
        self.engine.width = width
        self.engine.height = height
        self.engine.num_mines = mines
        self.engine.reset()
        self._normal_game_config = (width, height, mines)

        self._game_over = False
        self.reset_button.setText("🙂")
        self._reset_timer()
        self._reset_replay_recorder()

        self._build_grid()
        self._apply_initial_window_size()
        self.render_board()
        # 새 판 시작 → PLAYING 상태의 마스킹/초기 값으로 통계 패널 초기화
        self._update_statistics_panel(self.engine.get_stats())

    # ------------------------------------------------------------------
    # 클릭 핸들러
    # ------------------------------------------------------------------
    def _is_revealed_number(self, x: int, y: int) -> bool:
        """obs 기반으로 해당 칸이 '열린 숫자 칸'인지 판단."""
        value = self.engine.get_observation()[y][x]
        return value not in (
            CellState.HIDDEN.value, CellState.FLAGGED.value,
            CellState.MINE.value, CellState.EXPLODED.value,
            CellState.FALSE_FLAG.value,
        )

    def on_left_click(self, x: int, y: int):
        if self._replay_mode:
            return
        if self._game_over:
            return

        info = None
        if self._is_revealed_number(x, y):
            if self._chord_mode == ChordMode.LEFT_CLICK:
                _, _, _, _, info = self.engine.step(x, y, Action.CHORD)
                self._record_replay_event(x, y, Action.CHORD)
            else:
                return
        else:
            _, _, _, _, info = self.engine.step(x, y, Action.OPEN)
            self._start_timer()
            self._record_replay_event(x, y, Action.OPEN)

        self.render_board()
        self._apply_stats_from_info(info)
        self._check_end_state()

    def on_right_click(self, x: int, y: int):
        if self._replay_mode:
            return
        if self._game_over:
            return
        _, _, _, _, info = self.engine.step(x, y, Action.FLAG)
        self._start_timer()
        self._record_replay_event(x, y, Action.FLAG)
        self.render_board()
        self._apply_stats_from_info(info)

    def on_both_click(self, x: int, y: int):
        if self._replay_mode:
            return
        if self._game_over:
            return
        if self._chord_mode == ChordMode.DISABLED:
            return
        _, _, _, _, info = self.engine.step(x, y, Action.CHORD)
        self._record_replay_event(x, y, Action.CHORD)
        self.render_board()
        self._apply_stats_from_info(info)
        self._check_end_state()

    def on_reset(self):
        if self._replay_mode:
            return
        self.engine.reset()
        self._game_over = False
        self.reset_button.setText("🙂")
        self._reset_timer()
        self._reset_replay_recorder()
        self.render_board()
        # 리셋 직후에는 PLAYING 상태이므로 마스킹/초기 값이 표시된다.
        self._update_statistics_panel(self.engine.get_stats())

    def _apply_stats_from_info(self, info: dict):
        """
        step()이 반환한 info 딕셔너리에서 'stats'를 꺼내 통계 패널에 반영한다.
        엔진이 이미 마스킹/포맷 규칙(PLAYING 중 "-/-" 및 정수 클릭,
        종료 시 "X + Y" 또는 "X")을 적용해 던지므로, UI는 받은 값을
        그대로 표시하기만 한다. 신규 Left/Right/Chord/CPS 항목도
        STAT_ROWS에 등록되어 있어 동일 경로로 자동 갱신된다.
        """
        if info and "stats" in info:
            self._update_statistics_panel(info["stats"])

    # ------------------------------------------------------------------
    # 렌더링 (엔진 -> UI)
    # ------------------------------------------------------------------
    def render_board(self):
        """engine.get_observation() 결과만으로 전체 보드를 다시 그린다."""
        obs = self.engine.get_observation()
        font_size = self._current_font_size()
        border = border_width_for(self._cell_size)

        for y in range(self.engine.height):
            for x in range(self.engine.width):
                self._render_cell(self._buttons[(x, y)], obs[y][x], font_size, border)

        remaining = self.engine.num_mines - self.engine.count_flags()
        self.mine_label.setText(f"💣 {remaining:03d}")

    def _current_font_size(self) -> int:
        """셀 크기에 비례한 폰트 크기."""
        return max(6, int(self._cell_size * 0.5))

    def _render_cell(self, btn: CellButton, value: int, font_size: int, border: int):
        """단일 셀 표시값에 따라 텍스트/색상/폰트 적용 (obs 값만 사용)."""
        font = QFont("Arial", font_size, QFont.Bold)
        btn.setFont(font)

        if value == CellState.HIDDEN.value:
            btn.setText("")
            btn.setStyleSheet(self._style_hidden(border))
        elif value == CellState.FLAGGED.value:
            btn.setText("🚩")
            btn.setStyleSheet(self._style_hidden(border))
        elif value == CellState.FALSE_FLAG.value:
            # 패배 시 오답 깃발: 연한 빨강 배경으로 명확히 구분
            btn.setText("🚩")
            btn.setStyleSheet(self._style_false_flag())
        elif value == CellState.EXPLODED.value:
            btn.setText("💥")
            btn.setStyleSheet(self._style_exploded())
        elif value == CellState.MINE.value:
            btn.setText("💣")
            btn.setStyleSheet(self._style_revealed())
        elif value == 0:
            btn.setText("")
            btn.setStyleSheet(self._style_revealed())
        else:  # 1 ~ 8
            btn.setText(str(value))
            color = NUMBER_COLORS.get(value, "#000000")
            btn.setStyleSheet(self._style_revealed(color=color))

    # 스타일 헬퍼 (셀 크기 단계별 고정 테두리 적용) ---------------------
    @staticmethod
    def _style_hidden(border: int):
        """
        닫힌 칸 스타일.
        - 1px: 플랫(solid #ffffff, 밝은 톤 유지)
        - 2~3px: 입체(outset #ffffff)
        """
        if border == 1:
            border_style = "border: 1px solid #ffffff;"
        else:
            border_style = f"border: {border}px outset #ffffff;"
        return (
            "QPushButton {"
            " background-color: #c0c0c0;"
            f" {border_style}"
            " margin: 0px; padding: 0px;"
            "}"
            "QPushButton:hover { background-color: #d0d0d0; }"
        )

    @staticmethod
    def _style_revealed(color: str = "#000000"):
        """열린 칸 스타일. 입체감 불필요하므로 1px solid로 통일."""
        return (
            "QPushButton {"
            " background-color: #e0e0e0;"
            " border: 1px solid #a0a0a0;"
            f" color: {color};"
            " margin: 0px; padding: 0px;"
            "}"
        )

    @staticmethod
    def _style_exploded():
        """폭발 칸 스타일."""
        return (
            "QPushButton {"
            " background-color: #ff0000;"
            " border: 1px solid #a0a0a0;"
            " margin: 0px; padding: 0px;"
            "}"
        )

    @staticmethod
    def _style_false_flag():
        """오답 깃발 칸 스타일: 연한 빨강 배경으로 일반 지뢰와 구분."""
        return (
            "QPushButton {"
            " background-color: #ffcccc;"
            " border: 1px solid #a0a0a0;"
            " margin: 0px; padding: 0px;"
            "}"
        )

    # ------------------------------------------------------------------
    # 게임 종료 처리 (QMessageBox 없이 시각적 표현만)
    # ------------------------------------------------------------------
    def _check_end_state(self):
        status = self.engine.status
        if status == GameStatus.LOST:
            self._game_over = True
            self._stop_timer()
            self.reset_button.setText("😵")
            self.render_board()
        elif status == GameStatus.WON:
            self._game_over = True
            self._stop_timer()
            self.reset_button.setText("😎")
            self.render_board()
