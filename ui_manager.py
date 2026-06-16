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

import os
import pickle
import subprocess
import sys
import tempfile
import time
from bisect import bisect_right
from datetime import datetime
from enum import IntEnum

from PyQt5.QtWidgets import (
    QWidget, QPushButton, QGridLayout, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QSizePolicy, QShortcut, QInputDialog,
    QSpinBox, QDoubleSpinBox, QScrollArea, QSlider,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
    QFileDialog, QMessageBox, QStyle, QStyleOptionSlider,
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QPoint, QSize
from PyQt5.QtGui import QFont, QKeySequence, QColor, QIcon, QPainter, QPixmap, QPolygon

from core_engine import MinesweeperEngine, CellState, GameStatus, Action
from replay_json import load_replay_json, save_replay_json
from replay_player import ReplayPlayer
from replay_recorder import ReplayRecorder
from zini_calculator import ZiniNeighborhoodBeamConfig


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
REPLAY_TIME_TICK_INTERVAL_MS = 20
REPLAY_INDEX_INTERVAL_MIN_MS = 20
REPLAY_INDEX_INTERVAL_MAX_MS = 5000
REPLAY_SPEED_MIN = 0.25
REPLAY_SPEED_MAX = 8.0
REPLAY_MODE_INDEX = "Index"
REPLAY_MODE_TIME = "Time"
REPLAY_ICON_SIZE = QSize(24, 24)
STATS_PANEL_WIDTH = 170
ZINI_WORKER_SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "zini_metric_worker.py",
)
ZINI_WORKER_TERMINATE_TIMEOUT_SECONDS = 1.0


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
    ("efficiency",      "Efficiency",     "-"),
    ("ioe",             "IOE",            "-"),
    ("ops",             "Ops",            "0/0"),
    ("thrp",            "Thrp",           "-"),
    ("corr",            "Corr",           "-"),
    ("zini",            "ZiNi",           "-"),
    ("zne",             "ZNE",            "-"),
    ("znt",             "ZNT",            "-"),
]

COUNTER_METRIC_KEYS = (
    "efficiency",
    "ioe",
    "thrp",
    "corr",
    "zini",
    "zne",
    "znt",
)
ZINI_COUNTER_CONFIG = ZiniNeighborhoodBeamConfig(
    ranking_policy="standard_seeded_chain_v1",
    max_evaluations=1000,
    standard_phase_evaluations=500,
    max_seconds=None,
    stall_seconds=None,
    seed=0,
)


def _draw_replay_icon(kind: str, color: QColor) -> QPixmap:
    pixmap = QPixmap(REPLAY_ICON_SIZE)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(color)

    def rect(x: int, y: int, width: int, height: int):
        painter.drawRect(x, y, width, height)

    def triangle(points: list[tuple[int, int]]):
        painter.drawPolygon(QPolygon([QPoint(x, y) for x, y in points]))

    if kind == "first":
        rect(2, 4, 4, 16)
        triangle([(15, 4), (7, 12), (15, 20)])
        triangle([(22, 4), (14, 12), (22, 20)])
    elif kind == "previous":
        rect(4, 4, 4, 16)
        triangle([(19, 4), (9, 12), (19, 20)])
    elif kind == "play":
        triangle([(7, 4), (19, 12), (7, 20)])
    elif kind == "pause":
        rect(6, 4, 4, 16)
        rect(14, 4, 4, 16)
    elif kind == "next":
        triangle([(5, 4), (15, 12), (5, 20)])
        rect(17, 4, 4, 16)
    elif kind == "last":
        triangle([(2, 4), (10, 12), (2, 20)])
        triangle([(9, 4), (17, 12), (9, 20)])
        rect(18, 4, 4, 16)

    painter.end()
    return pixmap


def _replay_icon(kind: str) -> QIcon:
    icon = QIcon()
    icon.addPixmap(_draw_replay_icon(kind, QColor("#202020")), QIcon.Normal, QIcon.Off)
    icon.addPixmap(_draw_replay_icon(kind, QColor("#9a9a9a")), QIcon.Disabled, QIcon.Off)
    return icon


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


class JumpSlider(QSlider):
    """Horizontal slider that jumps to the clicked track position."""

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            option = QStyleOptionSlider()
            self.initStyleOption(option)
            handle_rect = self.style().subControlRect(
                QStyle.CC_Slider,
                option,
                QStyle.SC_SliderHandle,
                self,
            )
            if not handle_rect.contains(event.pos()):
                self.setValue(self._value_from_x(event.x(), handle_rect.width()))
                event.accept()
                return
        super().mousePressEvent(event)

    def _value_from_x(self, x: int, handle_width: int) -> int:
        span = max(1, self.width() - handle_width)
        ratio = (x - handle_width / 2) / span
        ratio = max(0.0, min(1.0, ratio))
        if self.invertedAppearance():
            ratio = 1.0 - ratio
        return round(self.minimum() + ratio * (self.maximum() - self.minimum()))


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
        self._replay_data = None
        self._replay_slider_updating = False
        self._replay_time_anchor_wall = None
        self._replay_time_anchor_replay = 0.0
        self._replay_display_time_override = None
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
        self._last_replay_directory = None

        # 통계 패널의 값 셀(QTableWidgetItem)을 stat_key로 보관.
        # _update_statistics_panel() 이 이 매핑을 통해 값을 갱신한다.
        self._replay_autoplay_timer = QTimer(self)
        self._replay_autoplay_timer.setInterval(REPLAY_AUTOPLAY_INTERVAL_MS)
        self._replay_autoplay_timer.timeout.connect(self._advance_replay_autoplay)
        self._stat_value_items = {}
        self._zini_job_token = 0
        self._zini_result_token = None
        self._zini_result_clicks = None
        self._zini_process = None
        self._zini_process_token = None
        self._zini_payload_path = None
        self._zini_result_path = None
        self._zini_poll_timer = QTimer(self)
        self._zini_poll_timer.setInterval(100)
        self._zini_poll_timer.timeout.connect(self._poll_zini_metric_job)

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

    def closeEvent(self, event):
        """Stop any running ZiNi worker when the UI is closing."""
        self._terminate_zini_metric_process()
        super().closeEvent(event)

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

        self.current_replay_button = QPushButton("이번 판 Replay")
        self.current_replay_button.setFocusPolicy(Qt.NoFocus)
        self.current_replay_button.clicked.connect(self.on_view_current_replay)

        self.save_replay_button = QPushButton("Replay 저장")
        self.save_replay_button.setFocusPolicy(Qt.NoFocus)
        self.save_replay_button.clicked.connect(self.on_save_replay)

        self.save_replay_as_button = QPushButton("Replay 다른 이름으로 저장")
        self.save_replay_as_button.setFocusPolicy(Qt.NoFocus)
        self.save_replay_as_button.clicked.connect(self.on_save_replay_as)

        self.load_replay_button = QPushButton("Replay 불러오기")
        self.load_replay_button.setFocusPolicy(Qt.NoFocus)
        self.load_replay_button.clicked.connect(self.on_load_replay)

        self.replay_status_label = QLabel()
        self.replay_status_label.setFont(QFont("Consolas", 10, QFont.Bold))
        self.replay_status_label.setVisible(False)

        self.replay_play_button = QPushButton()
        self.replay_play_button.setFocusPolicy(Qt.NoFocus)
        self.replay_play_button.clicked.connect(self.on_replay_play_pause)
        self.replay_play_button.setVisible(False)

        self.replay_first_button = QPushButton()
        self.replay_first_button.setFocusPolicy(Qt.NoFocus)
        self.replay_first_button.clicked.connect(self.on_replay_first)
        self.replay_first_button.setVisible(False)

        self.replay_prev_button = QPushButton()
        self.replay_prev_button.setFocusPolicy(Qt.NoFocus)
        self.replay_prev_button.clicked.connect(self.on_replay_previous)
        self.replay_prev_button.setVisible(False)

        self.replay_next_button = QPushButton()
        self.replay_next_button.setFocusPolicy(Qt.NoFocus)
        self.replay_next_button.clicked.connect(self.on_replay_next)
        self.replay_next_button.setVisible(False)

        self.replay_last_button = QPushButton()
        self.replay_last_button.setFocusPolicy(Qt.NoFocus)
        self.replay_last_button.clicked.connect(self.on_replay_last)
        self.replay_last_button.setVisible(False)

        self.exit_replay_button = QPushButton("Replay 종료")
        self.exit_replay_button.setFocusPolicy(Qt.NoFocus)
        self.exit_replay_button.clicked.connect(self.on_exit_replay)
        self.exit_replay_button.setVisible(False)

        self.replay_playback_mode_combo = QComboBox()
        self.replay_playback_mode_combo.addItems([REPLAY_MODE_INDEX, REPLAY_MODE_TIME])
        self.replay_playback_mode_combo.setFocusPolicy(Qt.NoFocus)
        self.replay_playback_mode_combo.currentTextChanged.connect(
            self.on_replay_playback_mode_changed
        )

        self.replay_index_interval_spin = QSpinBox()
        self.replay_index_interval_spin.setRange(
            REPLAY_INDEX_INTERVAL_MIN_MS,
            REPLAY_INDEX_INTERVAL_MAX_MS,
        )
        self.replay_index_interval_spin.setValue(REPLAY_AUTOPLAY_INTERVAL_MS)
        self.replay_index_interval_spin.setSuffix(" ms")
        self.replay_index_interval_spin.setFocusPolicy(Qt.ClickFocus)
        self.replay_index_interval_spin.valueChanged.connect(
            self.on_replay_index_interval_changed
        )

        self.replay_time_speed_spin = QDoubleSpinBox()
        self.replay_time_speed_spin.setRange(REPLAY_SPEED_MIN, REPLAY_SPEED_MAX)
        self.replay_time_speed_spin.setDecimals(2)
        self.replay_time_speed_spin.setSingleStep(0.25)
        self.replay_time_speed_spin.setValue(1.0)
        self.replay_time_speed_spin.setSuffix("x")
        self.replay_time_speed_spin.setFocusPolicy(Qt.ClickFocus)
        self.replay_time_speed_spin.valueChanged.connect(
            self.on_replay_time_speed_changed
        )

        self.replay_mode_save_button = QPushButton("저장")
        self.replay_mode_save_button.setFocusPolicy(Qt.NoFocus)
        self.replay_mode_save_button.clicked.connect(self.on_save_replay)

        self.replay_mode_save_as_button = QPushButton("다른 이름")
        self.replay_mode_save_as_button.setFocusPolicy(Qt.NoFocus)
        self.replay_mode_save_as_button.clicked.connect(self.on_save_replay_as)

        self.replay_slider = JumpSlider(Qt.Horizontal)
        self.replay_slider.setFocusPolicy(Qt.NoFocus)
        self.replay_slider.setMinimum(0)
        self.replay_slider.setMaximum(0)
        self.replay_slider.setValue(0)
        self.replay_slider.setMinimumWidth(180)
        self.replay_slider.valueChanged.connect(self.on_replay_slider_changed)

        self._configure_replay_icon_button(self.replay_first_button, "first")
        self._configure_replay_icon_button(self.replay_prev_button, "previous")
        self._configure_replay_icon_button(self.replay_play_button, "play")
        self._configure_replay_icon_button(self.replay_next_button, "next")
        self._configure_replay_icon_button(self.replay_last_button, "last")

        top_bar.addWidget(self.mine_label)
        top_bar.addStretch()
        top_bar.addWidget(self.reset_button)
        top_bar.addStretch()
        top_bar.addWidget(self.timer_label)
        top_bar.addSpacing(12)
        top_bar.addWidget(self.current_replay_button)
        top_bar.addWidget(self.save_replay_button)
        top_bar.addWidget(self.save_replay_as_button)
        top_bar.addWidget(self.load_replay_button)
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

        self.replay_control_bar = QWidget()
        self.replay_control_bar.setVisible(False)
        replay_control_layout = QHBoxLayout(self.replay_control_bar)
        replay_control_layout.setContentsMargins(0, 2, 0, 0)
        replay_control_layout.setSpacing(6)
        replay_control_layout.addWidget(self.replay_first_button)
        replay_control_layout.addWidget(self.replay_prev_button)
        replay_control_layout.addWidget(self.replay_play_button)
        replay_control_layout.addWidget(self.replay_next_button)
        replay_control_layout.addWidget(self.replay_last_button)
        replay_control_layout.addWidget(self.replay_playback_mode_combo)
        replay_control_layout.addWidget(self.replay_index_interval_spin)
        replay_control_layout.addWidget(self.replay_time_speed_spin)
        replay_control_layout.addWidget(self.replay_slider, 1)
        replay_control_layout.addWidget(self.replay_status_label)
        replay_control_layout.addWidget(self.replay_mode_save_button)
        replay_control_layout.addWidget(self.replay_mode_save_as_button)
        replay_control_layout.addWidget(self.exit_replay_button)
        main_layout.addWidget(self.replay_control_bar)

        return main_layout

    def _configure_replay_icon_button(self, button: QPushButton, icon_kind: str):
        button.setIcon(_replay_icon(icon_kind))
        button.setIconSize(REPLAY_ICON_SIZE)
        button.setFixedSize(34, 30)
        button.setText("")

    def _set_replay_play_icon(self, icon_kind: str):
        self.replay_play_button.setIcon(_replay_icon(icon_kind))

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
        if self.engine.status == GameStatus.PLAYING:
            self._update_live_time_stat(elapsed)

    def _update_live_time_stat(self, elapsed: float):
        """Update only the Counters Time value during the 10ms UI timer."""
        item = self._stat_value_items.get("time")
        if item is not None:
            item.setText(f"{elapsed:.1f}")

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
        merged_stats = dict(stats_dict)
        if self.engine.status != GameStatus.PLAYING:
            merged_stats.update(self._counter_metric_values())

        for key, value in merged_stats.items():
            item = self._stat_value_items.get(key)
            if item is not None:
                item.setText(str(value))

    def _counter_metric_values(self) -> dict[str, str]:
        """Return the seven Counters metrics using current engine state."""
        metrics = {key: "-" for key in COUNTER_METRIC_KEYS}
        counter_snapshot = self.engine.get_counter_snapshot()
        status = counter_snapshot["status"]

        if status == GameStatus.PLAYING:
            return metrics
        if status not in (GameStatus.LOST, GameStatus.WON):
            return metrics

        active_clicks = counter_snapshot["active_clicks"]
        wasted_clicks = counter_snapshot["wasted_clicks"]
        total_clicks = active_clicks + wasted_clicks
        completed_3bv = counter_snapshot["completed_3bv"]
        self._ensure_zini_metric_job()
        board_zini = self._current_zini_clicks()

        metrics["efficiency"] = self._format_counter_percent(
            completed_3bv,
            total_clicks,
        )
        metrics["ioe"] = self._format_counter_decimal(
            completed_3bv,
            total_clicks,
        )
        metrics["thrp"] = self._format_counter_decimal(
            completed_3bv,
            active_clicks,
        )
        metrics["corr"] = self._format_counter_decimal(
            active_clicks,
            total_clicks,
        )
        if board_zini is not None:
            metrics["zini"] = str(board_zini)

        if status == GameStatus.WON and board_zini is not None:
            metrics["zne"] = self._format_counter_decimal(
                board_zini,
                total_clicks,
            )
            metrics["znt"] = self._format_counter_decimal(
                board_zini,
                active_clicks,
            )

        return metrics

    def _reset_counter_metrics_for_board_change(self):
        """Reset cached/displayed Counters metrics for a new board."""
        self._reset_zini_metric_job()
        self._set_counter_metric_placeholders()

    def _set_counter_metric_placeholders(self):
        """Show placeholder values for metrics that are hidden while playing."""
        for key in COUNTER_METRIC_KEYS:
            item = self._stat_value_items.get(key)
            if item is not None:
                item.setText("-")

    def _reset_zini_metric_job(self):
        """Invalidate and stop any pending ZiNi calculation for a previous board."""
        self._zini_job_token += 1
        self._zini_result_token = None
        self._zini_result_clicks = None
        self._terminate_zini_metric_process()
        if self._zini_poll_timer.isActive():
            self._zini_poll_timer.stop()

    def _ensure_zini_metric_job(self):
        """Start bounded seeded-chain ZiNi calculation in a cancellable subprocess."""
        snapshot = self.engine.get_board_snapshot()
        if not snapshot.mines_placed:
            return
        if self._zini_result_token == self._zini_job_token:
            return
        if self._zini_process is not None:
            if (
                self._zini_process_token == self._zini_job_token
                and self._zini_process.poll() is None
            ):
                if not self._zini_poll_timer.isActive():
                    self._zini_poll_timer.start()
                return
            self._terminate_zini_metric_process()

        token = self._zini_job_token
        try:
            payload_path, result_path = self._create_zini_worker_files(
                token,
                snapshot,
            )
            process = subprocess.Popen(
                [sys.executable, ZINI_WORKER_SCRIPT, payload_path, result_path],
                cwd=os.path.dirname(ZINI_WORKER_SCRIPT),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            print(f"[ZiNi warning] counter ZiNi worker start failed: {exc}")
            self._cleanup_zini_worker_files(
                locals().get("payload_path"),
                locals().get("result_path"),
            )
            self._zini_result_token = token
            self._zini_result_clicks = None
            return

        self._zini_process = process
        self._zini_process_token = token
        self._zini_payload_path = payload_path
        self._zini_result_path = result_path
        if not self._zini_poll_timer.isActive():
            self._zini_poll_timer.start()

    def _create_zini_worker_files(self, token: int, snapshot) -> tuple[str, str]:
        """Write one subprocess payload and reserve one atomic result path."""
        payload_fd, payload_path = tempfile.mkstemp(
            prefix="minesweeper_zini_payload_",
            suffix=".pkl",
        )
        result_fd, result_path = tempfile.mkstemp(
            prefix="minesweeper_zini_result_",
            suffix=".pkl",
        )
        os.close(result_fd)
        os.remove(result_path)
        try:
            with os.fdopen(payload_fd, "wb") as payload_file:
                pickle.dump(
                    {
                        "token": token,
                        "snapshot": snapshot,
                        "config": ZINI_COUNTER_CONFIG,
                    },
                    payload_file,
                    protocol=pickle.HIGHEST_PROTOCOL,
                )
        except Exception:
            self._cleanup_zini_worker_files(payload_path, result_path)
            raise
        return payload_path, result_path

    def _terminate_zini_metric_process(self):
        """Terminate the active ZiNi subprocess and remove its temp files."""
        process = self._zini_process
        if process is not None:
            try:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=ZINI_WORKER_TERMINATE_TIMEOUT_SECONDS)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=ZINI_WORKER_TERMINATE_TIMEOUT_SECONDS)
                else:
                    process.wait(timeout=0)
            except Exception as exc:
                print(f"[ZiNi warning] counter ZiNi worker cleanup failed: {exc}")
        self._clear_zini_metric_process()

    def _clear_zini_metric_process(self):
        """Forget completed worker state and clean worker temp files."""
        self._cleanup_zini_worker_files(
            self._zini_payload_path,
            self._zini_result_path,
        )
        self._zini_process = None
        self._zini_process_token = None
        self._zini_payload_path = None
        self._zini_result_path = None

    def _cleanup_zini_worker_files(self, *paths):
        """Remove worker temp files, ignoring already-cleaned paths."""
        for path in paths:
            if not path:
                continue
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
            except OSError as exc:
                print(f"[ZiNi warning] temp file cleanup failed: {exc}")

    def _read_zini_worker_result(self) -> dict | None:
        """Read the completed subprocess result if it has been written."""
        if not self._zini_result_path or not os.path.exists(self._zini_result_path):
            return None
        try:
            with open(self._zini_result_path, "rb") as result_file:
                return pickle.load(result_file)
        except Exception as exc:
            print(f"[ZiNi warning] counter ZiNi result read failed: {exc}")
            return {
                "token": self._zini_process_token,
                "clicks": None,
                "error": repr(exc),
            }

    def _finish_zini_metric_process(self):
        """Reap a worker that already produced a result, then clear its files."""
        process = self._zini_process
        try:
            if process is not None and process.poll() is None:
                try:
                    process.wait(timeout=0.1)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try:
                        process.wait(timeout=ZINI_WORKER_TERMINATE_TIMEOUT_SECONDS)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=ZINI_WORKER_TERMINATE_TIMEOUT_SECONDS)
        except Exception as exc:
            print(f"[ZiNi warning] counter ZiNi worker cleanup failed: {exc}")
        self._clear_zini_metric_process()

    def _poll_zini_metric_job(self):
        """Apply completed ZiNi subprocess results on the UI thread."""
        if self._zini_process is None:
            self._zini_poll_timer.stop()
            return

        result = self._read_zini_worker_result()
        if result is None:
            if self._zini_process.poll() is None:
                return
            result = {
                "token": self._zini_process_token,
                "clicks": None,
                "error": f"worker exited with code {self._zini_process.returncode}",
            }

        token = result.get("token")
        if token == self._zini_job_token:
            if result.get("error"):
                print(f"[ZiNi warning] counter ZiNi calculation failed: {result['error']}")
            self._zini_result_token = token
            self._zini_result_clicks = result.get("clicks")
            self._update_statistics_panel(self.engine.get_stats())

        self._finish_zini_metric_process()
        if self._zini_process is None:
            self._zini_poll_timer.stop()

    def _current_zini_clicks(self) -> int | None:
        """Return the completed bounded best-so-far ZiNi value, if any."""
        if self._zini_result_token != self._zini_job_token:
            return None
        return self._zini_result_clicks

    @staticmethod
    def _format_counter_decimal(numerator: int, denominator: int) -> str:
        """Format a ratio metric or mask divide-by-zero as '-'."""
        if denominator == 0:
            return "-"
        return f"{numerator / denominator:.4f}"

    @staticmethod
    def _format_counter_percent(numerator: int, denominator: int) -> str:
        """Format Efficiency as an integer percentage."""
        if denominator == 0:
            return "-"
        return f"{numerator / denominator * 100:.0f}%"

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

    def _build_current_replay_data(
        self,
        title: str,
        require_finished: bool = False,
        allow_replay_mode: bool = False,
    ):
        """Return current replay data or show a user-facing reason it is unavailable."""
        if self._replay_mode:
            if allow_replay_mode and self._replay_player is not None:
                return self._replay_data or self._replay_player.replay_data
            QMessageBox.information(
                self,
                title,
                "Replay 모드에서는 현재 판 replay를 만들 수 없습니다.",
            )
            return None

        snapshot = self.engine.get_board_snapshot()
        if not snapshot.mines_placed:
            QMessageBox.information(
                self,
                title,
                "지뢰가 아직 배치되지 않아 replay를 만들 수 없습니다.",
            )
            return None

        if require_finished and self.engine.status == GameStatus.PLAYING:
            QMessageBox.information(
                self,
                title,
                "게임이 끝난 뒤 이번 판 Replay를 볼 수 있습니다.",
            )
            return None

        self._capture_replay_board_if_ready()
        try:
            return self._replay_recorder.to_replay_data()
        except ValueError as exc:
            QMessageBox.information(
                self,
                title,
                f"현재 판 replay를 만들 수 없습니다.\n{exc}",
            )
            return None

    def _remember_replay_directory(self, path: str):
        directory = os.path.dirname(os.path.abspath(path))
        if directory:
            self._last_replay_directory = directory

    def _replay_dialog_directory(self) -> str:
        if self._last_replay_directory and os.path.isdir(self._last_replay_directory):
            return self._last_replay_directory
        return ""

    def _append_json_extension(self, path: str) -> str:
        if not path.lower().endswith(".json"):
            return f"{path}.json"
        return path

    def _next_auto_replay_path(self, directory: str) -> str:
        base_name = datetime.now().strftime("replay_%Y%m%d_%H%M%S")
        path = os.path.join(directory, f"{base_name}.json")
        suffix = 1
        while os.path.exists(path):
            path = os.path.join(directory, f"{base_name}_{suffix}.json")
            suffix += 1
        return path

    def _save_replay_data(self, replay_data, path: str, title: str) -> bool:
        try:
            save_replay_json(replay_data, path)
        except Exception as exc:
            QMessageBox.warning(
                self,
                f"{title} 실패",
                f"Replay를 저장하지 못했습니다.\n{exc}",
            )
            return False

        self._remember_replay_directory(path)
        QMessageBox.information(
            self,
            title,
            f"Replay를 저장했습니다.\n{path}",
        )
        return True

    def _select_auto_replay_directory(self) -> str | None:
        directory = self._replay_dialog_directory()
        if directory:
            return directory

        selected = QFileDialog.getExistingDirectory(
            self,
            "Replay 저장 폴더 선택",
            "",
        )
        if not selected:
            return None
        self._last_replay_directory = selected
        return selected

    def on_view_current_replay(self):
        """Open the just-finished game in replay mode without saving a file."""
        replay_data = self._build_current_replay_data(
            "이번 판 Replay",
            require_finished=True,
        )
        if replay_data is None:
            return
        self._enter_replay_mode(ReplayPlayer(replay_data))

    def on_save_replay(self):
        """Save the current replay with a fresh timestamped filename."""
        replay_data = self._build_current_replay_data(
            "Replay 저장",
            allow_replay_mode=True,
        )
        if replay_data is None:
            return

        directory = self._select_auto_replay_directory()
        if not directory:
            return

        path = self._next_auto_replay_path(directory)
        self._save_replay_data(replay_data, path, "Replay 저장")

    def on_save_replay_as(self):
        """Save the current replay to a user-selected file."""
        replay_data = self._build_current_replay_data(
            "Replay 다른 이름으로 저장",
            allow_replay_mode=True,
        )
        if replay_data is None:
            return

        default_name = datetime.now().strftime("replay_%Y%m%d_%H%M%S.json")
        initial_path = os.path.join(self._replay_dialog_directory(), default_name)
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Replay 다른 이름으로 저장",
            initial_path,
            "Replay JSON (*.json);;All Files (*)",
        )
        if not path:
            return
        path = self._append_json_extension(path)

        if os.path.exists(path):
            reply = QMessageBox.question(
                self,
                "Replay 덮어쓰기 확인",
                f"이미 있는 파일입니다.\n덮어쓸까요?\n{path}",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        self._save_replay_data(replay_data, path, "Replay 다른 이름으로 저장")

    def on_load_replay(self):
        """JSON 리플레이 파일을 불러와 리플레이 모드로 진입한다."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "리플레이 불러오기",
            self._replay_dialog_directory(),
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

        self._remember_replay_directory(path)
        self._enter_replay_mode(replay_player)

    def on_exit_replay(self):
        """리플레이 모드를 끝내고 현재 선택된 난이도로 새 일반 게임을 시작한다."""
        self._exit_replay_mode()

    def _replay_playback_mode(self) -> str:
        return self.replay_playback_mode_combo.currentText()

    def _reset_replay_time_anchor(self):
        if self._replay_player is None:
            anchor_replay_time = 0.0
        else:
            anchor_replay_time = self._replay_display_time()
        self._replay_time_anchor_wall = time.perf_counter()
        self._replay_time_anchor_replay = anchor_replay_time

    def _start_replay_autoplay(self):
        if not self._replay_mode or self._replay_player is None:
            return
        if self._replay_player.current_index >= self._replay_player.event_count:
            return

        if self._replay_playback_mode() == REPLAY_MODE_TIME:
            self._reset_replay_time_anchor()
            self._clear_replay_display_time_override()
            self._replay_autoplay_timer.setInterval(REPLAY_TIME_TICK_INTERVAL_MS)
        else:
            self._replay_autoplay_timer.setInterval(
                self.replay_index_interval_spin.value()
            )
        self._replay_autoplay_timer.start()
        self._update_replay_controls()

    def on_replay_play_pause(self):
        if not self._replay_mode or self._replay_player is None:
            return

        if self._replay_player.current_index >= self._replay_player.event_count:
            self._stop_replay_autoplay()
            self._update_replay_controls()
            return

        if self._replay_autoplay_timer.isActive():
            self._stop_replay_autoplay(preserve_time_position=True)
            self._update_replay_controls()
        else:
            self._start_replay_autoplay()

    def _advance_replay_autoplay(self):
        if not self._replay_mode or self._replay_player is None:
            self._stop_replay_autoplay()
            return

        if self._replay_player.current_index >= self._replay_player.event_count:
            self._stop_replay_autoplay()
            self._update_replay_controls()
            return

        if self._replay_playback_mode() == REPLAY_MODE_TIME:
            self._advance_replay_autoplay_by_time()
        else:
            self._replay_player.next()
            self._refresh_replay_view_after_move()

        if self._replay_player.current_index >= self._replay_player.event_count:
            self._stop_replay_autoplay()
            self._update_replay_controls()

    def _advance_replay_autoplay_by_time(self):
        if self._replay_player is None:
            return
        if self._replay_time_anchor_wall is None:
            self._reset_replay_time_anchor()

        elapsed_wall = time.perf_counter() - self._replay_time_anchor_wall
        target_time = (
            self._replay_time_anchor_replay
            + elapsed_wall * self.replay_time_speed_spin.value()
        )
        advanced = False
        events = self._replay_player.replay_data.events
        while self._replay_player.current_index < self._replay_player.event_count:
            next_event = events[self._replay_player.current_index]
            if next_event.elapsed_time > target_time:
                break
            self._replay_player.next()
            advanced = True

        if advanced:
            self._refresh_replay_view_after_move()
        else:
            self._update_replay_status_label()
            self._sync_replay_slider()

    def _stop_replay_autoplay(self, preserve_time_position: bool = False):
        if self._replay_autoplay_timer.isActive():
            if (
                preserve_time_position
                and self._replay_playback_mode() == REPLAY_MODE_TIME
            ):
                self._set_replay_display_time_override(self._replay_display_time())
            self._replay_autoplay_timer.stop()
        self._replay_time_anchor_wall = None
        self._set_replay_play_icon("play")

    def on_replay_first(self):
        if not self._replay_mode or self._replay_player is None:
            return
        self._stop_replay_autoplay()
        self._clear_replay_display_time_override()
        self._replay_player.go_to(0)
        self._refresh_replay_view_after_move()

    def on_replay_previous(self):
        if not self._replay_mode or self._replay_player is None:
            return
        self._stop_replay_autoplay()
        self._clear_replay_display_time_override()
        self._replay_player.previous()
        self._refresh_replay_view_after_move()

    def on_replay_next(self):
        if not self._replay_mode or self._replay_player is None:
            return
        self._stop_replay_autoplay()
        self._clear_replay_display_time_override()
        self._replay_player.next()
        self._refresh_replay_view_after_move()

    def on_replay_last(self):
        if not self._replay_mode or self._replay_player is None:
            return
        self._stop_replay_autoplay()
        self._clear_replay_display_time_override()
        self._replay_player.go_to(self._replay_player.event_count)
        self._refresh_replay_view_after_move()

    def on_replay_slider_changed(self, value: int):
        if self._replay_slider_updating:
            return
        if not self._replay_mode or self._replay_player is None:
            return
        self._stop_replay_autoplay()
        if self._replay_playback_mode() == REPLAY_MODE_TIME:
            target_time = self._slider_value_to_replay_time(value)
            self._set_replay_display_time_override(target_time)
            self._replay_player.go_to(self._replay_index_for_time(target_time))
        else:
            self._clear_replay_display_time_override()
            self._replay_player.go_to(value)
        self._refresh_replay_view_after_move()

    def on_replay_playback_mode_changed(self, _mode: str):
        if self._replay_autoplay_timer.isActive():
            if self._replay_playback_mode() == REPLAY_MODE_TIME:
                self._reset_replay_time_anchor()
                self._clear_replay_display_time_override()
                self._replay_autoplay_timer.setInterval(REPLAY_TIME_TICK_INTERVAL_MS)
            else:
                self._clear_replay_display_time_override()
                self._replay_autoplay_timer.setInterval(
                    self.replay_index_interval_spin.value()
                )
        elif self._replay_playback_mode() == REPLAY_MODE_INDEX:
            self._clear_replay_display_time_override()
        self._update_replay_status_label()
        self._update_replay_controls()

    def on_replay_index_interval_changed(self, value: int):
        if (
            self._replay_autoplay_timer.isActive()
            and self._replay_playback_mode() == REPLAY_MODE_INDEX
        ):
            self._replay_autoplay_timer.setInterval(value)
        self._update_replay_status_label()

    def on_replay_time_speed_changed(self, _value: float):
        if (
            self._replay_autoplay_timer.isActive()
            and self._replay_playback_mode() == REPLAY_MODE_TIME
        ):
            self._reset_replay_time_anchor()
        self._update_replay_status_label()

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
        self._reset_counter_metrics_for_board_change()
        self._replay_mode = True
        self._replay_player = replay_player
        self._replay_data = replay_player.replay_data
        self._clear_replay_display_time_override()
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
        self._reset_counter_metrics_for_board_change()
        self._replay_mode = False
        self._replay_player = None
        self._replay_data = None
        self._clear_replay_display_time_override()
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
            f"{self._playback_status_prefix()} | "
            f"Step {self._replay_player.current_index}/"
            f"{self._replay_player.event_count} | "
            f"{self._replay_display_time():.3f}s"
        )

    def _replay_display_time(self) -> float:
        if (
            self._replay_playback_mode() == REPLAY_MODE_TIME
            and self._replay_autoplay_timer.isActive()
            and self._replay_time_anchor_wall is not None
            and self._replay_player is not None
        ):
            elapsed_wall = time.perf_counter() - self._replay_time_anchor_wall
            display_time = (
                self._replay_time_anchor_replay
                + elapsed_wall * self.replay_time_speed_spin.value()
            )
            return self._clamp_replay_display_time(display_time)
        if self._replay_player is None:
            return 0.0
        if (
            self._replay_playback_mode() == REPLAY_MODE_TIME
            and self._replay_display_time_override is not None
        ):
            return self._clamp_replay_display_time(
                self._replay_display_time_override
            )
        return self._replay_player.current_time

    def _last_replay_event_time(self) -> float:
        if self._replay_player is None or not self._replay_player.replay_data.events:
            return 0.0
        return self._replay_player.replay_data.events[-1].elapsed_time

    def _last_replay_event_time_ms(self) -> int:
        return max(0, int(self._last_replay_event_time() * 1000))

    def _replay_display_time_ms(self) -> int:
        return max(0, int(self._replay_display_time() * 1000))

    def _clamp_replay_display_time(self, replay_time: float) -> float:
        return max(0.0, min(replay_time, self._last_replay_event_time()))

    def _set_replay_display_time_override(self, replay_time: float):
        self._replay_display_time_override = self._clamp_replay_display_time(
            replay_time
        )

    def _clear_replay_display_time_override(self):
        self._replay_display_time_override = None

    def _replay_index_for_time(self, replay_time: float) -> int:
        if self._replay_player is None:
            return 0
        target_time = self._clamp_replay_display_time(replay_time)
        event_times = [
            event.elapsed_time for event in self._replay_player.replay_data.events
        ]
        return bisect_right(event_times, target_time)

    def _slider_value_to_replay_time(self, value: int) -> float:
        if value >= self.replay_slider.maximum():
            return self._last_replay_event_time()
        return self._clamp_replay_display_time(value / 1000.0)

    def _playback_status_prefix(self) -> str:
        if self._replay_playback_mode() == REPLAY_MODE_TIME:
            return f"Time {self._format_speed_value(self.replay_time_speed_spin.value())}x"
        return f"Index {self.replay_index_interval_spin.value()}ms"

    @staticmethod
    def _format_speed_value(value: float) -> str:
        return f"{value:.2f}".rstrip("0").rstrip(".")

    def _sync_replay_slider(self):
        previous_block = self.replay_slider.blockSignals(True)
        self._replay_slider_updating = True
        try:
            if self._replay_mode and self._replay_player is not None:
                if self._replay_playback_mode() == REPLAY_MODE_TIME:
                    max_time_ms = self._last_replay_event_time_ms()
                    self.replay_slider.setRange(0, max_time_ms)
                    self.replay_slider.setValue(
                        min(self._replay_display_time_ms(), max_time_ms)
                    )
                    self.replay_slider.setEnabled(max_time_ms > 0)
                else:
                    self.replay_slider.setRange(0, self._replay_player.event_count)
                    self.replay_slider.setValue(self._replay_player.current_index)
                    self.replay_slider.setEnabled(
                        self._replay_player.event_count > 0
                    )
            else:
                self.replay_slider.setRange(0, 0)
                self.replay_slider.setValue(0)
                self.replay_slider.setEnabled(False)
        finally:
            self._replay_slider_updating = False
            self.replay_slider.blockSignals(previous_block)

    def _update_replay_controls(self):
        """일반/리플레이 모드에 맞춰 버튼 상태를 갱신한다."""
        in_replay = self._replay_mode and self._replay_player is not None
        at_start = in_replay and self._replay_player.current_index == 0
        at_end = (
            in_replay
            and self._replay_player.current_index == self._replay_player.event_count
        )

        general_replay_controls_visible = not self._replay_mode
        self.reset_button.setEnabled(not self._replay_mode)
        self.current_replay_button.setVisible(general_replay_controls_visible)
        self.save_replay_button.setVisible(general_replay_controls_visible)
        self.save_replay_as_button.setVisible(general_replay_controls_visible)
        self.load_replay_button.setVisible(general_replay_controls_visible)
        self.current_replay_button.setEnabled(not self._replay_mode)
        self.save_replay_button.setEnabled(not self._replay_mode)
        self.save_replay_as_button.setEnabled(not self._replay_mode)
        self.load_replay_button.setEnabled(not self._replay_mode)
        self.difficulty_combo.setEnabled(not self._replay_mode)
        self.chord_combo.setEnabled(not self._replay_mode)
        self.cell_size_spin.setEnabled(not self._replay_mode)
        self.replay_control_bar.setVisible(in_replay)
        self.replay_status_label.setVisible(in_replay)
        self.replay_play_button.setVisible(in_replay)
        self.replay_play_button.setEnabled(in_replay and not at_end)
        self._set_replay_play_icon(
            "pause" if self._replay_autoplay_timer.isActive() else "play"
        )
        is_index_mode = self._replay_playback_mode() == REPLAY_MODE_INDEX
        self.replay_playback_mode_combo.setVisible(in_replay)
        self.replay_index_interval_spin.setVisible(in_replay and is_index_mode)
        self.replay_time_speed_spin.setVisible(in_replay and not is_index_mode)
        self.replay_first_button.setVisible(in_replay)
        self.replay_prev_button.setVisible(in_replay)
        self.replay_next_button.setVisible(in_replay)
        self.replay_last_button.setVisible(in_replay)
        self.replay_first_button.setEnabled(in_replay and not at_start)
        self.replay_prev_button.setEnabled(in_replay and not at_start)
        self.replay_next_button.setEnabled(in_replay and not at_end)
        self.replay_last_button.setEnabled(in_replay and not at_end)
        self.replay_mode_save_button.setVisible(in_replay)
        self.replay_mode_save_as_button.setVisible(in_replay)
        self.replay_mode_save_button.setEnabled(in_replay)
        self.replay_mode_save_as_button.setEnabled(in_replay)
        self.exit_replay_button.setVisible(self._replay_mode)
        self._sync_replay_slider()

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
        self._reset_counter_metrics_for_board_change()
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
        self._reset_counter_metrics_for_board_change()
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
