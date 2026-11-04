"""
ui_manager.py
PyQt5 기반 지뢰찾기 화면 및 인터페이스.

일반 게임의 기본 통계는 MinesweeperEngine이 제공하며,
ZiNi 기반 파생 지표는 엔진의 공개 counter snapshot과
ZiNi worker 결과를 사용해 UI 계층에서 조합한다.
Replay 통계는 ReplayStatisticsAnalyzer가 계산한다.
UI는 통계 결과를 표시하고 Replay 재생 상태를 관리한다.
engine.get_observation() 결과로 보드를 렌더링하며, Replay 재생 상태를 관리한다.

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
import time
from hashlib import sha256
from bisect import bisect_right
from dataclasses import dataclass, replace
from datetime import datetime
from enum import IntEnum
from uuid import uuid4

from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QGridLayout, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QSizePolicy, QShortcut, QInputDialog,
    QSpinBox, QDoubleSpinBox, QScrollArea, QSlider,
    QAbstractSpinBox, QLineEdit, QTextEdit, QPlainTextEdit,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
    QFileDialog, QMessageBox, QStyle, QStyleOptionSlider, QCheckBox, QMenu, QToolButton,
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QPoint, QSize, QEvent, QSettings
from PyQt5.QtGui import QFont, QKeySequence, QColor, QIcon, QPainter, QPixmap, QPolygon, QTextLayout, QTextOption

from core_engine import MinesweeperEngine, CellState, GameStatus, Action
from live_analysis import (
    CellOverlay, LiveAnalysis, OverlayKind, first_click_presentation,
    format_mine_probability, is_all_hidden, present_decision, reduced_number,
    present_v1_proposal, present_k_proposal, present_flag_preparation,
)
from live_policy import (
    POLICY_SIMPLE, POLICY_V1, POLICY_K, POLICY_K_LC0, POLICY_K_LC1, CANONICAL_NEW, ADOPT_CURRENT, PHASE_FLAG_REVIEW, PHASE_V1,
    admit_proposal, make_ack, make_snapshot, supports_v1_board, validate_ack,
)
from live_flag_review import report_to_dict
from live_simple_preparation import prepare_flags
from stage3_physical import action_cost, load_timing_table, PROFILE_SHA256, TABLE_SHA256
from live_policy_job import LivePolicyJob
from live_auto_cursor import LiveAutoCursorOverlay
import live_k_policy as k_live
from simple_algorithm import InconsistentObservationError
from simple_decision import DecisionKind, analyze_position
from replay_json import load_replay_json, save_replay_json
from replay_player import ReplayPlayer
from replay_model import SOURCE_HUMAN, SOURCE_ALGORITHM, SOURCE_AI
from replay_analysis import ReplayStepAnalysis, analyze_replay_step
from replay_display import recorded_input, reference_text, reference_overlays
from live_display_state import CertaintyFrame, DisplayContext
from replay_recorder import ReplayRecorder
from replay_statistics import ReplayStatisticsAnalyzer
from mouse_trace import MouseTraceRecorder
from mouse_trace_ui import MouseTraceOverlay
from zini_metric_job import (
    ZiniMetricJob, ZINI_COUNTER_CONFIG, ZINI_WORKER_SCRIPT,
    ZINI_WORKER_TERMINATE_TIMEOUT_SECONDS,
)
from zini_explorer import ZiniExplorerController


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
SIMPLE_AUTO_STEP_INTERVAL_MS = 180
MAX_DIMENSION = 100  # 커스텀 가로/세로 최대 칸 수


@dataclass(frozen=True)
class _KInputReceipt:
    """Seal of the completed input, independent of later manual board changes."""
    ack: object
    game_id: str
    history: tuple
    events: tuple
    action: tuple
    acknowledged: bool = False


_K_RECEIPT_FIELDS = (
    'game_id', 'run_id', 'board_generation', 'token', 'permit_nonce',
    'input_revision_before', 'input_revision_after', 'event_index',
    'action', 'x', 'y', 'before', 'after', 'status', 'cursor_after',
    'actual_input_confirmed', 'ack_sent',
    'policy_id', 'definition', 'entry_mode', 'start_input_revision', 'k_start_input_revision',
    'phase', 'preparation_seq', 'base_m_revision', 'pending_m_revision', 'M_before', 'preinput_M',
)

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


class LiveStatusLabel(QLabel):
    """A stable line budget; full diagnostic text stays available to readers."""

    def __init__(self, text, lines, *, hint="", parent=None):
        super().__init__(parent)
        self._lines = lines
        self._hint = hint
        self._screen = self._window_handle = None
        self.setTextFormat(Qt.PlainText)
        self.setWordWrap(False)
        self.setMargin(2)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self._sync_height()
        self.setText(text)

    def _sync_height(self, *_args):
        metrics = self.fontMetrics()
        margins = self.contentsMargins()
        line_height = max(metrics.height(), metrics.lineSpacing())
        if line_height <= 0:  # Offscreen platforms may have no usable font face.
            line_height = max(1, self.font().pixelSize(),
                              round(self.font().pointSizeF() * self.logicalDpiY() / 72))
        height = (line_height * self._lines
                  + 2 * (self.margin() + self.frameWidth())
                  + margins.top() + margins.bottom())
        self.setFixedHeight(height)
        self.update()

    def sizeHint(self):
        return QSize(0, self.height())

    def minimumSizeHint(self):
        return self.sizeHint()

    def hasHeightForWidth(self):
        return False

    def setText(self, text):
        super().setText(text)
        full = text + ("\n" + self._hint if self._hint else "")
        self.setToolTip(full)
        self.setAccessibleName(text)
        self.setAccessibleDescription(full)
        self.update()

    def _summary(self):
        text = self.text().replace(" (frozen)", "")
        if self._lines == 1 and text.startswith("현재:") and " | " in text:
            policy, state = text.split(" | ", 1)
            if "정리 실패" in state:
                state = "정리 실패 · " + state
            return state + " | " + policy.removeprefix("현재: ")
        if "깃발 확인/정리" in text and "미확인 깃발" in text:
            return "미확인 깃발은 실제 지뢰여도 해제될 수 있습니다.\n" + " | ".join(text.split(" | ", 2)[:2])
        if "미검증" in text and "깃발" in text:
            phase = "검토 중" if "검토 중" in text else "준비"
            warning = "미검증 깃발 해제 · 실제 지뢰일 수 있음"
            if any(word in text for word in ("오류", "실패", "불가", "중단")):
                warning = "오류 · " + warning
            return warning + "\n" + phase + " · " + text.split(" | ", 1)[0]
        if "추측 대기" in text:
            return "추측 대기 · 추측 허용 꺼짐\n" + text.split(" | 추측 대기", 1)[0]
        return text

    def display_text(self):
        """The exact bounded text painted, independent of QLabel's full text."""
        width = max(0, self.contentsRect().width() - 2 * self.margin())
        metrics = self.fontMetrics()
        paragraphs = self._summary().splitlines() or [""]
        result = []
        while paragraphs and len(result) < self._lines:
            paragraph = paragraphs.pop(0)
            if len(result) == self._lines - 1:
                result.append(metrics.elidedText(" ".join([paragraph, *paragraphs]), Qt.ElideRight, width))
                break
            layout = QTextLayout(paragraph, self.font())
            option = QTextOption()
            option.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
            layout.setTextOption(option)
            layout.beginLayout()
            line = layout.createLine()
            if line.isValid():
                line.setLineWidth(width)
                end = max(1, line.textLength())
                result.append(paragraph[:end].rstrip())
                if end < len(paragraph):
                    paragraphs.insert(0, paragraph[end:].lstrip())
            else:
                result.append("")
            layout.endLayout()
        return "\n".join(result)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(self.palette().color(self.foregroundRole()))
        rect = self.contentsRect().adjusted(self.margin(), self.margin(), -self.margin(), -self.margin())
        painter.drawText(rect, Qt.AlignLeft | Qt.AlignTop, self.display_text())

    def changeEvent(self, event):
        super().changeEvent(event)
        if hasattr(self, "_lines") and event.type() in (QEvent.FontChange, QEvent.ApplicationFontChange, QEvent.StyleChange):
            self._sync_height()

    def _screen_changed(self, screen):
        if self._screen is not None:
            try:
                self._screen.logicalDotsPerInchChanged.disconnect(self._sync_height)
            except (TypeError, RuntimeError):
                pass
        self._screen = screen
        if screen is not None:
            screen.logicalDotsPerInchChanged.connect(self._sync_height)
        self._sync_height()

    def showEvent(self, event):
        super().showEvent(event)
        handle = self.window().windowHandle()
        if handle is not None and handle is not self._window_handle:
            self._window_handle = handle
            handle.screenChanged.connect(self._screen_changed)
            self._screen_changed(handle.screen())


class CellButton(QPushButton):
    """
    Forward physical mouse events to the board gesture coordinator.
    Semantic click signals use the physical action's resolved press/release target.
    """
    mouse_input = pyqtSignal(object, object)
    left_clicked = pyqtSignal(int, int)
    right_clicked = pyqtSignal(int, int)
    both_clicked = pyqtSignal(int, int)

    def __init__(self, x: int, y: int, parent=None):
        super().__init__(parent)
        self.x = x
        self.y = y
        self.analysis_overlay = None
        self.recorded_target = False
        self.probability_text = ""
        self.setFocusPolicy(Qt.NoFocus)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setMouseTracking(True)

    def set_analysis_overlay(self, overlay: CellOverlay | None, show_probability=True,
                             *, recorded_target=False):
        """Presentation only: leave button text, style and mouse behavior intact."""
        probability_text = ""
        tooltip = []
        if recorded_target:
            tooltip.append("녹화된 다음 입력 셀")
        if overlay is not None:
            if overlay.recommended:
                tooltip.append("추천 셀")
            if overlay.kind == OverlayKind.SAFE:
                tooltip.append("안전 확정")
            elif overlay.kind == OverlayKind.MINE:
                tooltip.append("지뢰 확정")
            elif overlay.probability is not None:
                tooltip.append(f"지뢰 확률: {format_mine_probability(overlay.probability)}")
            if overlay.probability is not None and show_probability:
                probability_text = format_mine_probability(overlay.probability, compact=True)
        text = " · ".join(tooltip)
        if (self.analysis_overlay == overlay and self.probability_text == probability_text
                and self.recorded_target == recorded_target and self.toolTip() == text):
            return
        self.analysis_overlay = overlay
        self.recorded_target = recorded_target
        self.probability_text = probability_text
        self.setToolTip(text)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        overlay = self.analysis_overlay
        if overlay is None and not self.recorded_target:
            return
        overlay = overlay or CellOverlay()
        painter = QPainter(self)
        colors = {
            OverlayKind.SAFE: QColor(35, 185, 85, 105),
            OverlayKind.MINE: QColor(230, 45, 55, 110),
            OverlayKind.GUESS_CANDIDATE: QColor(255, 160, 20, 120),
        }
        if overlay.kind in colors:
            painter.fillRect(self.rect().adjusted(1, 1, -1, -1), colors[overlay.kind])
        if self.probability_text:
            painter.save()
            font = QFont("Arial")
            font.setBold(True)
            font.setPixelSize(max(8, int(self.width() * 0.44)))
            painter.setFont(font)
            metrics = painter.fontMetrics()
            text_width = max(1, metrics.horizontalAdvance(self.probability_text))
            text_height = max(1, metrics.height())
            # Keep compact percentages inside even 10px cells.
            scale = min(1.0, (self.width() - 4) / text_width,
                        (self.height() - 4) / text_height)
            painter.translate(self.rect().center())
            painter.scale(scale, scale)
            painter.setPen(QColor("#101010"))
            painter.drawText(-text_width // 2, -text_height // 2,
                             text_width + 1, text_height + 1,
                             Qt.AlignCenter, self.probability_text)
            painter.restore()
        if overlay.recommended or self.recorded_target:
            pen = painter.pen()
            pen.setWidth(2 if self.width() >= 20 else 1)
            pen.setColor(QColor("#ffffff"))
            painter.setPen(pen)
            painter.drawRect(self.rect().adjusted(1, 1, -2, -2))
            pen.setColor(QColor("#182965"))
            painter.setPen(pen)
            painter.drawRect(self.rect().adjusted(2, 2, -3, -3))
        painter.end()

    def mousePressEvent(self, event):
        # QWidget's default double-click handler also calls this method.
        # Avoid QPushButton's automatic down state, especially on flags.
        self.mouse_input.emit(self, event)
        event.accept()

    def mouseMoveEvent(self, event):
        self.mouse_input.emit(self, event)
        event.accept()

    def mouseReleaseEvent(self, event):
        self.mouse_input.emit(self, event)
        event.accept()


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

    live_action_applied = pyqtSignal(object)

    def __init__(self, engine: MinesweeperEngine):
        super().__init__()
        self.engine = engine
        self._benchmark_statistics_window = None
        self._stage3_visualizer_launcher = None
        self._same_board_comparison_launcher = None
        self._game_over = False
        self._buttons = {}
        self._mouse_buttons = Qt.NoButton
        self._mouse_left_suppressed = set()
        self._mouse_both = False  # Current Mode-B overlap awaits its first release.
        self._mouse_left_consumed = False  # Trailing LEFT release must be inert.
        self._mouse_position = None
        self._mouse_preview = set()
        self._mouse_trace_recorder = MouseTraceRecorder(engine.width, engine.height)
        self._mouse_trace_observation = None
        self._mouse_trace_recording_enabled = True
        self._mouse_trace_recording_locked = False
        self._mouse_trace_display_data = None
        self._analysis_result: LiveAnalysis | None = None
        self._certainty_frame = None
        self._replay_reference_error = None
        self._replay_analysis_result: ReplayStepAnalysis | None = None
        self._replay_view_index = None
        self._analysis_observation = None
        self._analysis_first_click = False
        self._simple_preparation = None
        self._simple_preparation_seq = 0
        self._simple_preparation_start = 0
        self._simple_review_dirty = True
        self._simple_expected_binding = None
        self._simple_analysis_binding = None
        self._simple_applying_preparation = False
        self._simple_timing_table = None
        self._simple_auto_pending = False
        self._simple_auto_timer = QTimer(self)
        self._simple_auto_timer.setSingleShot(True)
        self._simple_auto_timer.setInterval(SIMPLE_AUTO_STEP_INTERVAL_MS)
        self._simple_auto_timeout_slot = self._on_simple_auto_timeout
        self._simple_auto_timer.timeout.connect(self._simple_auto_timeout_slot)
        self._v1_timer_nonce = 0
        self._v1_timer_reservation = None
        self._live_policy = POLICY_SIMPLE
        self._live_board_generation = 0
        self._live_run_id = uuid4().hex
        self._live_game_id = uuid4().hex
        self._live_action_count = 0
        self._live_fresh_reset = (engine.status == GameStatus.PLAYING
                                  and is_all_hidden(engine.get_observation())
                                  and not engine.get_board_snapshot().mines_placed)
        self._live_history_known = self._live_fresh_reset
        self._live_input_uncertain = False
        self._live_closing = False
        self._live_close_error = None
        self._v1_cursor = (0, 0)
        self._v1_input_seq = 0
        self._v1_entry_mode = CANONICAL_NEW
        self._v1_phase = PHASE_V1
        self._v1_initial_flag_count = 0
        self._v1_review_inputs = 0
        self._v1_expected_ack = None
        self._k_ack_receipt = None
        self._k_retiring = None
        self._live_first_failure = None
        self.live_failure_records = []
        self._v1_pending = None
        self._v1_display_requested = False
        self._v1_owned = False
        self._v1_manual_only = False
        self._k_retired = False  # Failure latch only; normal retirement permits a new owner.
        self._k_reset_ready = False  # Explicit new-game/reset provenance, not merely all-HIDDEN.
        self._k_start_input_revision = 0
        self._k_phase = (k_live.normal_phase(self._live_policy)
                             if k_live.is_k_policy(self._live_policy) else k_live.PHASE_K)
        self._k_preparation_seq = 0
        self._k_normal_start = None
        self._k_bootstrap = None
        self._k_base_m = ()
        self._k_m_revision = 0
        self._k_validation_nonce = None
        self._v1_status = "수동 · Auto OFF"
        self._v1_job = self._create_v1_job()
        self.live_action_records = []
        self.live_owner_records = []
        self.live_input_records = []
        self.live_auto_totals = self._empty_live_auto_totals()
        self._chord_mode = ChordMode.LEFT_CLICK
        self._cell_size = DEFAULT_CELL_SIZE
        self._replay_mode = False
        self._replay_player = None
        self._replay_data = None
        self._replay_slider_updating = False
        self._replay_time_anchor_wall = None
        self._replay_time_anchor_replay = 0.0
        self._replay_display_time_override = None
        self._replay_counter_timeline = None
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
        self._replay_settings = QSettings("MinesweeperProject", "Minesweeper")

        # 통계 패널의 값 셀(QTableWidgetItem)을 stat_key로 보관.
        # _update_statistics_panel() 이 이 매핑을 통해 값을 갱신한다.
        self._replay_autoplay_timer = QTimer(self)
        self._replay_autoplay_timer.setInterval(REPLAY_AUTOPLAY_INTERVAL_MS)
        self._replay_autoplay_timer.timeout.connect(self._advance_replay_autoplay)
        self._stat_value_items = {}
        self._zini_job_token = 0
        self._zini_explorer = ZiniExplorerController()
        self._zini_explorer_window = None
        self._zini_job = ZiniMetricJob()
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
        self.installEventFilter(self)
        self._update_same_board_comparison_action()
        self._update_policy_controls()

    def closeEvent(self, event):
        """Close auxiliary windows and their workers before accepting shutdown."""
        self._live_closing = True
        self._invalidate_v1_run("창 닫기")
        try:
            self._v1_job.shutdown()
        except Exception as exc:
            if (self._v1_job.last_record is not None
                    and k_live.is_k_policy(self._v1_job.last_record.get('policy_id'))):
                self._on_v1_finished(self._v1_job.last_record)
            self._v1_status = f"정리 실패: {exc}"
            self._live_close_error = str(exc)
            self._update_policy_controls()
            event.ignore()
            return
        if (self._v1_job.last_record is not None
                and k_live.is_k_policy(self._v1_job.last_record.get('policy_id'))):
            # shutdown intentionally emits no signal. Bind its cleanup receipt
            # to retained K actions even when closing suppresses UI updates.
            self._on_v1_finished(self._v1_job.last_record)
        if self._same_board_comparison_launcher is not None:
            if not self._same_board_comparison_launcher.close():
                self._restore_after_auxiliary_close_refusal()
                event.ignore()
                return
        if self._stage3_visualizer_launcher is not None:
            if not self._stage3_visualizer_launcher.close():
                self._restore_after_auxiliary_close_refusal()
                event.ignore()
                return
        self._invalidate_mouse_input()
        self._mouse_trace_recorder.freeze()
        if self._benchmark_statistics_window is not None:
            self._benchmark_statistics_window.close()
        self._stop_simple_auto()
        self._reset_zini_metric_job()
        super().closeEvent(event)

    def hideEvent(self, event):
        self._invalidate_mouse_input()
        self._mouse_trace_recorder.break_segment()
        super().hideEvent(event)

    def eventFilter(self, watched, event):
        if (event.type() == QEvent.ShortcutOverride
                and event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter)
                and not self._game_shortcut_available()):
            # Leave editing, popup and modal keys with their original widget.
            event.accept()
            return True
        # Mouse observers do not consume input or split segments at ordinary
        # cell-to-cell crossings.
        if event.type() in (QEvent.Hide, QEvent.WindowDeactivate, QEvent.WindowBlocked):
            self._invalidate_mouse_input()
        if event.type() in (QEvent.Leave, QEvent.Hide, QEvent.Move, QEvent.Resize,
                            QEvent.WindowDeactivate, QEvent.WindowBlocked):
            self._mouse_trace_recorder.break_segment()
        return super().eventFilter(watched, event)

    def on_benchmark_statistics(self):
        """Own only the auxiliary viewer's lifetime; leave gameplay untouched."""
        from benchmark_statistics_ui import BenchmarkStatisticsWindow

        if self._benchmark_statistics_window is None:
            self._benchmark_statistics_window = BenchmarkStatisticsWindow(self)
        self._benchmark_statistics_window.show()
        self._benchmark_statistics_window.raise_()
        self._benchmark_statistics_window.activateWindow()

    def on_stage3_visualizer(self):
        """Open one independent benchmark launcher without touching gameplay."""
        if self._stage3_visualizer_launcher is None:
            from stage3_visualizer_launcher import Stage3VisualizerLauncherWindow

            self._stage3_visualizer_launcher = Stage3VisualizerLauncherWindow(self)
            self._stage3_visualizer_launcher.closed.connect(self._on_stage3_visualizer_closed)
        self._stage3_visualizer_launcher.show()
        self._stage3_visualizer_launcher.raise_()
        self._stage3_visualizer_launcher.activateWindow()

    def _on_stage3_visualizer_closed(self):
        if self.sender() is self._stage3_visualizer_launcher:
            self._stage3_visualizer_launcher = None

    def _update_same_board_comparison_action(self):
        """Source eligibility only; admission gives precise comparison rejections."""
        action = self.same_board_comparison_action
        if self._same_board_comparison_launcher is not None:
            action.setText("Open Comparison…")
            enabled = True
            explanation = "Open the Comparison launcher for its captured Human recording."
        else:
            action.setText("Compare as full-game Human Replay…")
            explanation = "Finish the current game or load a full-game Human Replay."
            if self._replay_mode:
                replay = self._replay_data
                if replay is None and self._replay_player is not None:
                    replay = self._replay_player.replay_data
                enabled = replay is not None and replay.source_type == SOURCE_HUMAN
                if replay is not None and not enabled:
                    explanation = "Same-board Comparison requires a Human-labeled Replay."
            else:
                enabled = (
                    self.engine.status in (GameStatus.WON, GameStatus.LOST)
                    and self.engine.get_board_snapshot().mines_placed
                    and self._replay_recorder.source_type == SOURCE_HUMAN
                )
                if self._replay_recorder.source_type != SOURCE_HUMAN:
                    explanation = "자동 입력이 포함된 판은 Human Replay 비교 대상이 아닙니다."
            if enabled:
                explanation = "Submit the entire recording as a full-game Human Replay for comparison."
        action.setEnabled(enabled)
        action.setToolTip(explanation)
        action.setStatusTip(explanation)

    def on_same_board_comparison(self):
        """Explicit declaration captures one full Replay; never follows later source changes."""
        try:
            if self._same_board_comparison_launcher is None:
                from same_board_comparison import HumanComparisonContext
                from same_board_comparison_launcher import SameBoardComparisonLauncherWindow

                source_description = (
                    "currently loaded Replay" if self._replay_mode else "completed current game"
                )
                replay = self._build_current_replay_data(
                    "Same-board Comparison", require_finished=True, allow_replay_mode=True,
                )
                if replay is None:
                    return
                # Activation of this deliberately named command is caller intent,
                # not provenance proof. Admission still requires Human metadata.
                context = HumanComparisonContext(replay, declared_full_game_human=True)
                launcher = SameBoardComparisonLauncherWindow(
                    context, self, source_description=source_description,
                )
                launcher.closed.connect(self._on_same_board_comparison_closed)
                self._same_board_comparison_launcher = launcher
                self._update_same_board_comparison_action()
            self._same_board_comparison_launcher.show()
            self._same_board_comparison_launcher.raise_()
            self._same_board_comparison_launcher.activateWindow()
        except Exception as exc:
            # Comparison eligibility does not change ordinary Replay validity.
            QMessageBox.information(
                self, "Same-board Comparison",
                f"Cannot use this Replay for Same-board Comparison\n{exc}",
            )

    def _on_same_board_comparison_closed(self):
        if self.sender() is self._same_board_comparison_launcher:
            self._same_board_comparison_launcher = None
            self._update_same_board_comparison_action()

    def _engine_for_current_mode(self) -> MinesweeperEngine:
        """Return the current Replay engine without replacing the live engine."""
        if self._replay_mode and self._replay_player is not None:
            return self._replay_player.engine
        return self.engine

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

        self.zini_explorer_button = QPushButton("ZiNi Explorer")
        self.zini_explorer_button.setEnabled(False)
        self.zini_explorer_button.clicked.connect(self.on_open_zini_explorer)
        layout.addWidget(self.zini_explorer_button)

        self.stage3_visualizer_button = QPushButton("Stage-3 Visualizer")
        self.stage3_visualizer_button.clicked.connect(self.on_stage3_visualizer)
        layout.addWidget(self.stage3_visualizer_button)

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
        self.tools_button = QToolButton()
        self.tools_button.setText("도구")
        self.tools_button.setPopupMode(QToolButton.InstantPopup)
        tools_menu = QMenu(self.tools_button)
        self.benchmark_statistics_action = tools_menu.addAction("벤치마크 통계")
        self.benchmark_statistics_action.triggered.connect(self.on_benchmark_statistics)
        self.replay_directory_action = tools_menu.addAction("Replay 저장 폴더...")
        self.replay_directory_action.triggered.connect(self.on_replay_directory)
        self.same_board_comparison_action = tools_menu.addAction("Compare as full-game Human Replay…")
        self.same_board_comparison_action.triggered.connect(self.on_same_board_comparison)
        self.tools_button.setMenu(tools_menu)
        settings_bar.addWidget(self.tools_button)
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

        policy_bar = QHBoxLayout()
        self.live_policy_label = QLabel("Auto 알고리즘:")
        self.live_policy_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        policy_bar.addWidget(self.live_policy_label)
        self.live_policy_combo = QComboBox()
        self.live_policy_combo.addItem("Stage2 Simple", POLICY_SIMPLE)
        self.live_policy_combo.addItem("Stage3 V1", POLICY_V1)
        self.live_policy_combo.addItem("K-P0 (실험적)", POLICY_K)
        self.live_policy_combo.addItem("K-LC0 (실험적)", POLICY_K_LC0)
        self.live_policy_combo.addItem("K-LC1 (실험적)", POLICY_K_LC1)
        self.live_policy_combo.setToolTip("정책 변경은 Auto를 멈춥니다. 다음 Auto ON부터 현재 판에 적용합니다.")
        self.live_policy_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.live_policy_combo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.live_policy_combo.currentIndexChanged.connect(self._on_live_policy_changed)
        self.live_policy_new_game_button = QPushButton("선택 정책으로 새 게임")
        self.live_policy_new_game_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.live_policy_new_game_button.clicked.connect(self.on_reset)
        self.live_policy_status_label = LiveStatusLabel("현재: Stage2 Simple", 1)
        policy_bar.addWidget(self.live_policy_combo)
        policy_bar.addWidget(self.live_policy_new_game_button)
        policy_bar.addStretch()
        main_layout.addLayout(policy_bar)
        # A full-width fixed status row keeps the state readable on narrow
        # windows instead of competing with the policy selection buttons.
        main_layout.addWidget(self.live_policy_status_label)

        analysis_bar = QHBoxLayout()
        self.analysis_checkbox = QCheckBox("분석 표시")
        self.probability_checkbox = QCheckBox("확률 표시")
        self.probability_checkbox.setChecked(True)
        self.reduction_checkbox = QCheckBox("Reduction")
        self.analyze_button = QPushButton("현재 상태 분석")
        self.simple_auto_checkbox = QCheckBox("확정 수 자동 진행")
        self.simple_auto_interval_spin = QSpinBox()
        self.simple_auto_interval_spin.setRange(0, 2000)
        self.simple_auto_interval_spin.setSingleStep(10)
        self.simple_auto_interval_spin.setSuffix(" ms")
        self.simple_auto_interval_spin.setSpecialValueText("최대 속도")
        self.simple_auto_interval_spin.setValue(SIMPLE_AUTO_STEP_INTERVAL_MS)
        self.simple_auto_interval_spin.setToolTip("입력 사이 관람 간격입니다. 계산 시간·게임 시간·Model C와 다릅니다.")
        self.simple_auto_interval_spin.setFocusPolicy(Qt.ClickFocus)
        self.simple_auto_interval_spin.valueChanged.connect(self.on_simple_auto_interval_changed)
        self.simple_auto_interval_spin.lineEdit().textEdited.connect(
            self._on_simple_auto_interval_edited)
        self.auto_interval_label = QLabel("자동 간격:")
        self.auto_interval_label.setBuddy(self.simple_auto_interval_spin)
        self.allow_guess_checkbox = QCheckBox("추측 허용")
        self.allow_guess_checkbox.setToolTip("Auto 일시정지는 선택을 보관합니다. 수동 전환·정책 변경·오류·새 게임에서는 해제됩니다.")
        self.allow_guess_checkbox.setEnabled(False)
        self.analyze_button.setFocusPolicy(Qt.NoFocus)
        self.analysis_checkbox.setToolTip("현재 보드를 분석하고 사용자 액션 후 자동 갱신")
        self.probability_checkbox.setToolTip("계산된 정확한 지뢰 확률이 있을 때만 숫자 표시")
        self.reduction_checkbox.setToolTip("열린 숫자를 화면에서만 N − 인접 깃발 수로 표시")
        self.analyze_button.setToolTip("한 번 분석하여 표시 (추천 액션은 실행하지 않음)")
        self.analysis_checkbox.toggled.connect(self.on_analysis_toggled)
        self.probability_checkbox.toggled.connect(self._render_live_analysis)
        self.reduction_checkbox.toggled.connect(self.render_board)
        self.analyze_button.clicked.connect(self.on_analyze_current)
        self.simple_auto_checkbox.toggled.connect(self.on_simple_auto_toggled)
        self.allow_guess_checkbox.toggled.connect(self.on_allow_guess_toggled)
        for control in (self.analysis_checkbox, self.probability_checkbox,
                        self.reduction_checkbox, self.analyze_button,
                        self.simple_auto_checkbox, self.auto_interval_label,
                        self.simple_auto_interval_spin, self.allow_guess_checkbox):
            analysis_bar.addWidget(control)
        analysis_bar.addStretch()
        main_layout.addLayout(analysis_bar)
        self.analysis_status_label = LiveStatusLabel(
            "분석 대기", 2,
            hint="초록: SAFE | 빨강: MINE | 주황: 최소 지뢰 확률 후보 | 테두리: 실제 추천")
        main_layout.addWidget(self.analysis_status_label)

        mouse_trace_bar = QHBoxLayout()
        self.mouse_trace_record_checkbox = QCheckBox("마우스 경로 기록")
        self.mouse_trace_record_checkbox.setChecked(self._mouse_trace_recording_enabled)
        self.mouse_trace_record_checkbox.setToolTip("첫 OPEN/FLAG 전에 선택 · 게임 종료 후 경로 확인")
        self.mouse_trace_record_checkbox.toggled.connect(self._on_mouse_trace_recording_toggled)
        self.mouse_trace_display_checkbox = QCheckBox("마우스 경로 표시")
        self.mouse_trace_display_checkbox.setEnabled(False)
        self.mouse_trace_display_checkbox.setToolTip("종료된 게임 / Replay에 기록된 전체 경로 표시 · 파랑 OPEN / 초록 FLAG / 보라 CHORD")
        self.mouse_trace_display_checkbox.toggled.connect(self._update_mouse_trace_controls)
        mouse_trace_bar.addWidget(self.mouse_trace_record_checkbox)
        mouse_trace_bar.addWidget(self.mouse_trace_display_checkbox)
        self.auto_cursor_checkbox = QCheckBox("자동 커서 표시")
        self.auto_cursor_checkbox.setChecked(True)
        self.auto_cursor_checkbox.setToolTip("V1/K 자동 입력의 가상 원형 커서 · 실제 마우스 경로와 별도")
        self.auto_cursor_checkbox.toggled.connect(self._on_auto_cursor_display_toggled)
        mouse_trace_bar.addWidget(self.auto_cursor_checkbox)
        mouse_trace_bar.addStretch()
        main_layout.addLayout(mouse_trace_bar)

        # --- 보드: 컨테이너 위젯 + 그리드, QScrollArea로 감싸기 ---
        self.board_container = QWidget()
        self.grid = QGridLayout(self.board_container)
        self.grid.setSpacing(0)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.mouse_trace_overlay = MouseTraceOverlay(self.board_container)
        self.auto_cursor_overlay = LiveAutoCursorOverlay(self.board_container)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.board_container)
        self.scroll_area.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.scroll_area.setWidgetResizable(False)
        for widget in (self.board_container, self.scroll_area.viewport()):
            widget.setMouseTracking(True)
            widget.installEventFilter(self)
        for scrollbar in (self.scroll_area.horizontalScrollBar(),
                          self.scroll_area.verticalScrollBar()):
            scrollbar.valueChanged.connect(self._break_mouse_trace_segment)
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
        self._invalidate_mouse_input()
        self._mouse_trace_recorder.break_segment()
        for btn in self._buttons.values():
            self.grid.removeWidget(btn)
            btn.deleteLater()
        self._buttons.clear()

        engine = self._engine_for_current_mode()
        for y in range(engine.height):
            for x in range(engine.width):
                btn = CellButton(x, y)
                btn.setFixedSize(self._cell_size, self._cell_size)
                btn.mouse_input.connect(self._on_cell_mouse_input)
                btn.left_clicked.connect(self.on_left_click)
                btn.right_clicked.connect(self.on_right_click)
                btn.both_clicked.connect(self.on_both_click)
                self.grid.addWidget(btn, y, x)
                self._buttons[(x, y)] = btn

        self._resize_board_container()

    def _resize_board_container(self):
        """보드 컨테이너를 셀 크기 x 칸 수에 딱 맞게 고정."""
        engine = self._engine_for_current_mode()
        w = engine.width * self._cell_size
        h = engine.height * self._cell_size
        self.board_container.setFixedSize(w, h)
        self.mouse_trace_overlay.setGeometry(0, 0, w, h)
        self.mouse_trace_overlay.set_cell_size(self._cell_size)
        self.mouse_trace_overlay.raise_()
        self.auto_cursor_overlay.setGeometry(0, 0, w, h)
        self.auto_cursor_overlay.set_cell_size(self._cell_size)
        self.auto_cursor_overlay.raise_()

    def _apply_initial_window_size(self):
        """초기 창 크기를 보드 비율에 맞춰 설정(화면 초과 시 적당히 제한)."""
        engine = self._engine_for_current_mode()
        board_w = engine.width * self._cell_size
        board_h = engine.height * self._cell_size
        # Reserve space for settings, game controls, policy/analysis/trace controls,
        # and scroll-area frames so the default expert board fits on first show.
        w = min(board_w + STATS_PANEL_WIDTH + 80, 1500)
        h = min(board_h + 290, 900)
        self.resize(w, h)

    def _init_shortcuts(self):
        """Route one key press according to the current Live/Replay mode."""
        for key in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            sc = QShortcut(QKeySequence(key), self)
            sc.setContext(Qt.WindowShortcut)
            sc.setAutoRepeat(False)
            sc.activated.connect(lambda key=key: self._on_game_shortcut(key))

    def _game_shortcut_available(self):
        if (self._live_closing or QApplication.activeModalWidget() is not None
                or QApplication.activePopupWidget() is not None):
            return False
        focus = QApplication.focusWidget()
        while focus is not None and focus is not self:
            if isinstance(focus, (QAbstractSpinBox, QLineEdit, QTextEdit, QPlainTextEdit)):
                return False
            if isinstance(focus, QComboBox) and focus.isEditable():
                return False
            focus = focus.parentWidget()
        return True

    def _on_game_shortcut(self, key):
        if not self._game_shortcut_available():
            return
        if self._replay_mode:
            if key == Qt.Key_Space and self.replay_play_button.isEnabled():
                self.replay_play_button.click()
            return
        self.on_reset()

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
        self._sync_zini_explorer_eligibility()
        merged_stats = dict(stats_dict)
        if self.engine.status != GameStatus.PLAYING:
            merged_stats.update(self._counter_metric_values())

        self._set_statistics_panel_values(merged_stats)

    def _set_statistics_panel_values(self, stats_dict: dict):
        """Apply already-formatted statistic values to visible STAT_ROWS."""
        for key, value in stats_dict.items():
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
        self._close_zini_explorer_window()
        self._zini_job_token += 1
        self._zini_explorer.invalidate()
        self._update_zini_explorer_button()
        self._terminate_zini_metric_process()
        if self._zini_poll_timer.isActive():
            self._zini_poll_timer.stop()

    def _zini_explorer_is_eligible(self) -> bool:
        """Use the same completed-game policy as Counters, regardless of seek."""
        if self._replay_mode:
            timeline = self._replay_counter_timeline
            return (
                self._replay_player is not None
                and timeline is not None
                and timeline.is_completed
            )
        return self.engine.status in (GameStatus.WON, GameStatus.LOST)

    def _sync_zini_explorer_eligibility(self):
        self._zini_explorer.set_eligible(
            self._zini_explorer.token == self._zini_job_token
            and self._zini_explorer_is_eligible()
        )
        self._update_zini_explorer_button()

    def _update_zini_explorer_button(self):
        usable = self._zini_explorer.state == "ready"
        self.zini_explorer_button.setEnabled(usable)
        if not usable:
            self._close_zini_explorer_window()

    def _close_zini_explorer_window(self):
        window = self._zini_explorer_window
        self._zini_explorer_window = None
        if window is not None:
            window.close()

    def _on_zini_explorer_closed(self):
        # A close preserves the controller's cached trace and logical position.
        if self.sender() is self._zini_explorer_window:
            self._zini_explorer_window = None

    def on_open_zini_explorer(self):
        """Open one auxiliary viewer at the explicit lazy-build boundary."""
        trace = self.request_zini_explorer_trace()
        if trace is None:
            if self._zini_explorer.eligible and self._zini_explorer.error is not None:
                QMessageBox.warning(
                    self, "ZiNi Explorer", "현재 ZiNi 결과의 경로를 표시할 수 없습니다.",
                )
            return

        if self._zini_explorer_window is None:
            from zini_explorer_ui import ZiniExplorerWindow

            self._zini_explorer_window = ZiniExplorerWindow(self._zini_explorer, self)
            self._zini_explorer_window.closed.connect(self._on_zini_explorer_closed)
        self._zini_explorer_window.show()
        self._zini_explorer_window.raise_()
        self._zini_explorer_window.activateWindow()

    def request_zini_explorer_trace(self):
        """Explicit, non-visual Explorer entry; never starts or repeats search.

        Counters never call this method. The pure controller owns the cached
        trace/player; the integrating caller is responsible for execution thread.
        """
        self._sync_zini_explorer_eligibility()
        trace = self._zini_explorer.request_trace()
        self._update_zini_explorer_button()
        return trace

    # Compatibility views for existing UI integration diagnostics. Ownership is
    # exclusively in the shared job; these do not implement a second lifecycle.
    @property
    def _zini_process(self):
        return self._zini_job.process

    @_zini_process.setter
    def _zini_process(self, process):
        self._zini_job.process = process

    @property
    def _zini_process_token(self):
        return self._zini_job.token

    @property
    def _zini_payload_path(self):
        return self._zini_job.payload_path

    @property
    def _zini_result_path(self):
        return self._zini_job.result_path

    def _ensure_zini_metric_job(self):
        """Precompute fixed boards; Counter/Explorer completion policy stays here."""
        self._sync_zini_explorer_eligibility()
        if (self._zini_explorer.token == self._zini_job_token
                and self._zini_explorer.completed):
            return
        if self._zini_job.active:
            if self._zini_job.token == self._zini_job_token:
                self._zini_poll_timer.start()
                return
            self._terminate_zini_metric_process()
        snapshot = self._engine_for_current_mode().get_board_snapshot()
        if not snapshot.mines_placed:
            return
        token = self._zini_job_token
        self._zini_explorer.begin(
            token, snapshot, eligible=self._zini_explorer_is_eligible(),
        )
        self._update_zini_explorer_button()
        self._zini_job.start(snapshot, token)
        self._zini_poll_timer.start()
        if self._zini_job.process is None:
            # A launch failure is delivered once, just like a worker failure.
            self._poll_zini_metric_job()

    def _terminate_zini_metric_process(self):
        error = self._zini_job.close()
        if error:
            print(f"[ZiNi warning] counter ZiNi worker cleanup failed: {error}")

    def _finish_zini_metric_process(self):
        """Leave completed Explorer/Counter policy state intact."""
        self._terminate_zini_metric_process()

    def _poll_zini_metric_job(self):
        token = self._zini_job.token
        result = self._zini_job.poll()
        if result is None:
            if not self._zini_job.active:
                self._zini_poll_timer.stop()
            return
        self._sync_zini_explorer_eligibility()
        if self._zini_explorer.receive(result, expected_token=token):
            if self._zini_explorer.error:
                print(f"[ZiNi warning] {self._zini_explorer.error}")
            if self._replay_mode:
                self._update_replay_statistics_panel()
            else:
                self._update_statistics_panel(self.engine.get_stats())
        self._finish_zini_metric_process()
        if not self._zini_job.active:
            self._zini_poll_timer.stop()

    def _current_zini_clicks(self) -> int | None:
        """Return the completed bounded best-so-far ZiNi value, if any."""
        if self._zini_explorer.token != self._zini_job_token:
            return None
        return self._zini_explorer.clicks

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

    def _clear_replay_counter_state(self):
        """Clear cached replay analyzer output for replay-mode statistics."""
        self._replay_counter_timeline = None

    def _prepare_replay_counter_state(self, replay_data):
        """Build replay counter timeline through the pure analyzer."""
        self._clear_replay_counter_state()
        try:
            timeline = ReplayStatisticsAnalyzer.analyze(replay_data)
        except Exception as exc:
            print(f"[Replay warning] counter timeline build failed: {exc}")
            return

        self._replay_counter_timeline = timeline

    def _update_replay_statistics_panel(self):
        """Update Counters from replay timeline instead of live-game masking."""
        self._set_statistics_panel_values(self._build_replay_statistics())

    def _build_replay_statistics(self) -> dict[str, str]:
        self._sync_zini_explorer_eligibility()
        timeline = self._replay_counter_timeline
        if timeline is None or self._replay_player is None:
            return ReplayStatisticsAnalyzer.masked_statistics()

        board_zini = None
        if timeline.is_completed:
            self._ensure_zini_metric_job()
            board_zini = self._current_zini_clicks()

        return ReplayStatisticsAnalyzer.statistics_at(
            timeline=timeline,
            index=self._replay_player.current_index,
            replay_time=self._replay_display_time(),
            board_zini=board_zini,
        )

    # ------------------------------------------------------------------
    # 리플레이 기록/저장
    # ------------------------------------------------------------------
    def _reset_replay_recorder(self):
        """현재 엔진 설정 기준으로 한 판 리플레이 기록을 초기화한다."""
        self._replay_recorder.reset(
            width=self.engine.width,
            height=self.engine.height,
            num_mines=self.engine.num_mines,
            source_type=SOURCE_HUMAN,
        )
        # Replacing the capture session also rejects a physical dispatch that
        # was interrupted by a reset/rebuild callback.
        self._mouse_trace_recorder = MouseTraceRecorder(self.engine.width, self.engine.height)
        self._mouse_trace_observation = None
        self._mouse_trace_recording_locked = False
        self._clear_mouse_trace_display()
        self._update_mouse_trace_controls()

    def _record_replay_event(self, x: int, y: int, action: Action):
        """engine.step()으로 실제 처리된 클릭 이벤트를 recorder에 반영한다."""
        event_index = None
        try:
            self._replay_recorder.record_event(
                elapsed_time=self.engine.get_elapsed_time(),
                x=x,
                y=y,
                action=action,
            )
            event_index = len(self._replay_recorder.events) - 1
            self._capture_replay_board_if_ready()
        except Exception as exc:
            # 리플레이 기록 실패가 기존 게임 플레이를 중단시키지 않도록 한다.
            print(f"[Replay warning] 이벤트 기록 실패: {exc}")
        return event_index

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
            replay_data = self._replay_recorder.to_replay_data()
            trace = self._mouse_trace_recorder.snapshot()
            # Save takes a detached prefix without freezing ongoing Live capture.
            if trace is not None and replay_data.source_type == SOURCE_HUMAN:
                replay_data = replace(replay_data, schema_version=2, mouse_trace=trace)
            return replay_data
        except ValueError as exc:
            QMessageBox.information(
                self,
                title,
                f"현재 판 replay를 만들 수 없습니다.\n{exc}",
            )
            return None

    def _replay_dialog_directory(self) -> str:
        """Use the configured save folder only while it is available."""
        directory = self._replay_settings.value("replay/default_directory", "")
        if isinstance(directory, str) and os.path.isdir(directory):
            return directory
        return ""

    def on_replay_directory(self) -> str | None:
        """Change the default only through an explicit directory selection."""
        # A directory dialog runs a nested event loop, just like Save/Load.
        self._stop_simple_auto()
        selected = QFileDialog.getExistingDirectory(
            self,
            "Replay 저장 폴더 선택",
            self._replay_dialog_directory(),
        )
        if not selected or not os.path.isdir(selected):
            return None
        self._replay_settings.setValue("replay/default_directory", selected)
        self._replay_settings.sync()
        return selected

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

        return self.on_replay_directory()

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
        self._stop_simple_auto()
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
        self._stop_simple_auto()
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
        self._stop_simple_auto()
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
            self._update_replay_statistics_panel()
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
            self._update_replay_statistics_panel()
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
        if self._replay_mode:
            self._update_replay_statistics_panel()
        self._update_replay_controls()

    def on_replay_index_interval_changed(self, value: int):
        if (
            self._replay_autoplay_timer.isActive()
            and self._replay_playback_mode() == REPLAY_MODE_INDEX
        ):
            self._replay_autoplay_timer.setInterval(value)
        self._update_replay_status_label()
        if self._replay_mode:
            self._update_replay_statistics_panel()

    def on_replay_time_speed_changed(self, _value: float):
        if (
            self._replay_autoplay_timer.isActive()
            and self._replay_playback_mode() == REPLAY_MODE_TIME
        ):
            self._reset_replay_time_anchor()
        self._update_replay_status_label()
        if self._replay_mode:
            self._update_replay_statistics_panel()

    def _refresh_replay_view_after_move(self):
        if self._replay_player is None:
            return
        changed = self._replay_view_index != self._replay_player.current_index
        if changed:
            self._clear_live_analysis()
        self._replay_view_index = self._replay_player.current_index
        self.render_board()
        self._update_replay_statistics_panel()
        self._update_replay_status_label()
        self._update_replay_controls()
        # Time autoplay reaches here once per tick, after all due events. Slider
        # sync and seeks within the same index must not repeat exact probability.
        if (changed and self.analysis_checkbox.isChecked()
                and self._replay_player.engine.status == GameStatus.PLAYING):
            self.on_analyze_current()
        self._render_live_analysis()

    def _enter_replay_mode(self, replay_player: ReplayPlayer):
        """ReplayPlayer의 초기 상태를 UI에 표시한다."""
        self._invalidate_v1_run("Replay 진입")
        self._invalidate_mouse_input()
        self._mouse_trace_recorder.invalidate()
        self._mouse_trace_observation = None
        self._clear_mouse_trace_display()
        self.mouse_trace_record_checkbox.setEnabled(False)
        self._stop_simple_auto()
        self._clear_live_analysis()
        self._replay_view_index = None
        self._normal_game_config = (
            self.engine.width,
            self.engine.height,
            self.engine.num_mines,
        )
        self._reset_counter_metrics_for_board_change()
        self._replay_mode = True
        self._replay_player = replay_player
        self._replay_data = replay_player.replay_data
        self.mouse_trace_overlay.set_trace(self._replay_data.mouse_trace, self._replay_data.events)
        self._clear_replay_display_time_override()
        self._prepare_replay_counter_state(replay_player.replay_data)
        self._game_over = False
        self.reset_button.setText("🙂")
        self._reset_timer()

        self._build_grid()
        self._apply_initial_window_size()
        self._refresh_replay_view_after_move()

        self._update_same_board_comparison_action()
        self._update_policy_controls()

    def _exit_replay_mode(self):
        """일반 플레이 모드로 돌아가 현재 선택 난이도로 새 게임을 시작한다."""
        self._invalidate_v1_run("Replay 종료")
        self._invalidate_mouse_input()
        self._stop_simple_auto()
        self._clear_live_analysis()
        self._stop_replay_autoplay()
        self._reset_counter_metrics_for_board_change()
        self._replay_mode = False
        self._replay_player = None
        self._replay_view_index = None
        self._replay_data = None
        self._clear_replay_display_time_override()
        self._clear_replay_counter_state()
        self._update_replay_controls()

        width, height, mines = self._normal_game_config
        self.engine.configure(width=width, height=height, num_mines=mines)
        self._prepare_live_policy_game()
        self._game_over = False
        self.reset_button.setText("🙂")
        self._reset_timer()
        self._reset_replay_recorder()
        self._build_grid()
        self._apply_initial_window_size()
        self._refresh_live_board()
        self._update_statistics_panel(self.engine.get_stats())

        self._update_same_board_comparison_action()

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
        for control in (self.analysis_checkbox, self.probability_checkbox,
                        self.reduction_checkbox, self.analyze_button):
            control.setEnabled(True)
        self.simple_auto_checkbox.setEnabled(not self._replay_mode)
        self.simple_auto_interval_spin.setEnabled(not self._replay_mode)
        self.allow_guess_checkbox.setEnabled(
            not self._replay_mode and self.simple_auto_checkbox.isChecked()
        )
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
        self._update_policy_controls()
        self._sync_replay_slider()

    # ------------------------------------------------------------------
    # 설정 핸들러
    # ------------------------------------------------------------------
    def on_chord_mode_changed(self, index: int):
        self._invalidate_mouse_input()
        self._chord_mode = ChordMode(index)
        self._update_mouse_preview()

    def on_cell_size_changed(self, value: int):
        """셀 크기 변경 시 모든 버튼과 컨테이너를 갱신."""
        self._invalidate_mouse_input()
        self._mouse_trace_recorder.break_segment()
        self._cell_size = value
        for btn in self._buttons.values():
            btn.setFixedSize(value, value)
        self._resize_board_container()
        self.render_board()

    def on_difficulty_changed(self, text: str):
        self._invalidate_v1_run("난이도 변경")
        self._invalidate_mouse_input()
        self._mouse_trace_recorder.break_segment()
        # Stop before a custom-difficulty dialog starts a nested Qt event loop.
        self._stop_simple_auto()
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
        self._invalidate_v1_run("새 보드")
        self._invalidate_mouse_input()
        self._stop_simple_auto()
        self._clear_live_analysis()
        self._reset_counter_metrics_for_board_change()
        self.engine.configure(width=width, height=height, num_mines=mines)
        self._prepare_live_policy_game()
        self._normal_game_config = (width, height, mines)

        self._game_over = False
        self.reset_button.setText("🙂")
        self._reset_timer()
        self._reset_replay_recorder()

        self._build_grid()
        self._apply_initial_window_size()
        self._refresh_live_board()
        # 새 판 시작 → PLAYING 상태의 마스킹/초기 값으로 통계 패널 초기화
        self._update_statistics_panel(self.engine.get_stats())
        self._update_same_board_comparison_action()

    # ------------------------------------------------------------------
    # 클릭 핸들러
    # ------------------------------------------------------------------
    def _break_mouse_trace_segment(self, _value=None):
        self._mouse_trace_recorder.break_segment()

    def _on_mouse_trace_recording_toggled(self, checked):
        if (self._mouse_trace_recording_locked or self._replay_mode
                or self.engine.status != GameStatus.PLAYING):
            blocked = self.mouse_trace_record_checkbox.blockSignals(True)
            self.mouse_trace_record_checkbox.setChecked(self._mouse_trace_recording_enabled)
            self.mouse_trace_record_checkbox.blockSignals(blocked)
        else:
            self._mouse_trace_recording_enabled = checked

    def _lock_mouse_trace_recording(self):
        self._mouse_trace_recording_locked = True
        self.mouse_trace_record_checkbox.setEnabled(False)

    def _clear_mouse_trace_display(self):
        self._mouse_trace_display_data = None
        self.mouse_trace_overlay.set_trace(None, ())
        self.mouse_trace_overlay.hide()
        blocked = self.mouse_trace_display_checkbox.blockSignals(True)
        self.mouse_trace_display_checkbox.setChecked(False)
        self.mouse_trace_display_checkbox.blockSignals(blocked)
        self.mouse_trace_display_checkbox.setEnabled(False)

    def _update_mouse_trace_controls(self, _checked=None):
        terminal_live = (not self._replay_mode
                         and self.engine.status in (GameStatus.WON, GameStatus.LOST))
        self.mouse_trace_record_checkbox.setEnabled(
            not self._replay_mode and not terminal_live and not self._mouse_trace_recording_locked)
        if (terminal_live and self._mouse_trace_recorder.frozen
                and self._mouse_trace_display_data is None):
            self._mouse_trace_display_data = self._mouse_trace_recorder.snapshot()
            self.mouse_trace_overlay.set_trace(self._mouse_trace_display_data,
                                              self._replay_recorder.events)
        if self._replay_mode:
            # ReplayData owns the entire attachment, independent of seek/time.
            available = self._replay_data is not None and self._replay_data.mouse_trace is not None
        else:
            available = terminal_live and self._mouse_trace_display_data is not None
        self.mouse_trace_display_checkbox.setEnabled(available)
        if not available:
            self._clear_mouse_trace_display()
        self.mouse_trace_overlay.setVisible(available and self.mouse_trace_display_checkbox.isChecked())

    def _mouse_trace_position(self, event):
        recorder = self._mouse_trace_recorder
        if (self._replay_mode or self.engine.status != GameStatus.PLAYING
                or not recorder.eligible or recorder.frozen or not self.isActiveWindow()
                or not self.board_container.isVisible()
                or QApplication.activeModalWidget() is not None):
            recorder.break_segment()
            return None
        # QScrollArea owns the board directly under its viewport. Map once to
        # board space and derive viewport coordinates from the board's offset.
        # Keep Qt's integer childAt test as well as the original floating bounds:
        # rounding at a clipped edge and disabled/stale children still matter.
        board = self.board_container
        viewport = self.scroll_area.viewport()
        global_position = event.globalPos()
        local = board.mapFromGlobal(global_position)
        offset_x, offset_y = board.x(), board.y()
        view_width, view_height = viewport.width(), viewport.height()
        if not (0 <= local.x() + offset_x < view_width
                and 0 <= local.y() + offset_y < view_height):
            recorder.break_segment()
            return None
        cell = board.childAt(local)
        if (not isinstance(cell, CellButton) or not cell.isEnabled()
                or self._buttons.get((cell.x, cell.y)) is not cell):
            recorder.break_segment()
            return None
        # Preserve the delivered subpixel position; global coordinates are only
        # used to map into board space and are never retained in trace data.
        position = event.screenPos()
        origin_x = global_position.x() - local.x()
        origin_y = global_position.y() - local.y()
        x, y = position.x() - origin_x, position.y() - origin_y
        if not (0 <= x < self.engine.width * self._cell_size
                and 0 <= y < self.engine.height * self._cell_size
                and 0 <= position.x() - (origin_x - offset_x) < view_width
                and 0 <= position.y() - (origin_y - offset_y) < view_height):
            recorder.break_segment()
            return None
        return x, y

    def _emit_mouse_action(self, target, signal_name, position, observed_ns):
        # This context exists only during the existing synchronous semantic
        # dispatch. Direct/Auto calls cannot borrow a previous observation.
        self._mouse_trace_observation = (
            (self._mouse_trace_recorder, position, self._cell_size, observed_ns)
            if position is not None else None
        )
        try:
            getattr(target, signal_name).emit(target.x, target.y)
        finally:
            self._mouse_trace_observation = None

    def _set_mouse_preview(self, cells):
        for cell in self._mouse_preview - cells:
            self._buttons[cell].setDown(False)
        for cell in cells - self._mouse_preview:
            self._buttons[cell].setDown(True)
        self._mouse_preview = cells

    def _invalidate_mouse_input(self):
        """Old releases cannot act on a reset, rebuilt, hidden or replay board."""
        self._set_mouse_preview(set())
        self._mouse_buttons = Qt.NoButton
        self._mouse_left_suppressed = set()
        self._mouse_both = False
        self._mouse_left_consumed = False
        self._mouse_position = None

    def _cell_at_mouse_position(self, global_position):
        # Qt grabs the original pressed widget until all buttons are released.
        # Resolve from global position, also excluding clipped/scrolled cells.
        viewport = self.scroll_area.viewport()
        if not viewport.rect().contains(viewport.mapFromGlobal(global_position)):
            return None
        cell = self.board_container.childAt(
            self.board_container.mapFromGlobal(global_position))
        if (isinstance(cell, CellButton) and cell.isEnabled()
                and self._buttons.get((cell.x, cell.y)) is cell):
            return cell
        return None

    def _update_mouse_preview(self):
        cells = set()
        if (self._mouse_buttons & Qt.LeftButton
                and not self._replay_mode and not self._game_over
                and self.engine.status == GameStatus.PLAYING
                and self._mouse_position is not None):
            target = self._cell_at_mouse_position(self._mouse_position)
            if target is not None:
                obs = self.engine.get_observation()
                x, y = target.x, target.y
                value = obs[y][x]
                if value == CellState.HIDDEN and not self._mouse_both:
                    cells.add((x, y))
                elif ((self._mouse_both and (value in (CellState.HIDDEN, CellState.FLAGGED) or 0 <= value <= 8))
                      or (0 <= value <= 8 and self._chord_mode == ChordMode.LEFT_CLICK)):
                    # No flag-count validation: this previews an attempt only.
                    cells = {
                        (nx, ny)
                        for ny in range(max(0, y - 1), min(len(obs), y + 2))
                        for nx in range(max(0, x - 1), min(len(obs[ny]), x + 2))
                        if obs[ny][nx] == CellState.HIDDEN
                    }
        self._set_mouse_preview(cells)

    def _on_cell_mouse_input(self, source, event):
        if (self._buttons.get((source.x, source.y)) is not source
                or self._replay_mode or self._game_over or not self.isVisible()
                or self._live_closing):
            return
        kind = event.type()
        button = event.button()
        buttons = event.buttons() & (Qt.LeftButton | Qt.RightButton)
        press = kind in (QEvent.MouseButtonPress, QEvent.MouseButtonDblClick)
        if press:
            if button not in (Qt.LeftButton, Qt.RightButton):
                return
            # Only a fresh transition can join the tracked hold. In particular,
            # a second press after invalidation cannot revive an old hold.
            if self._mouse_buttons & button or buttons != self._mouse_buttons | button:
                self._invalidate_mouse_input()
                return
        elif kind == QEvent.MouseButtonRelease:
            if not self._mouse_buttons & button:
                return
            if buttons != self._mouse_buttons & ~button:
                self._invalidate_mouse_input()
                return
        elif kind != QEvent.MouseMove:
            return

        # Retire before changing the hold or capturing physical evidence, then
        # continue the original gesture. No synthetic click is generated here.
        if press and self._cell_at_mouse_position(event.globalPos()) is not None:
            self._retire_v1_for_manual("보드 입력으로 수동 인계")
            if self._live_policy == POLICY_SIMPLE:
                self._cancel_simple_auto_step()

        right_action = (press and button == Qt.RightButton
                        and not (self._chord_mode == ChordMode.BOTH_CLICK
                                 and self._mouse_buttons & Qt.LeftButton))
        action_observation = right_action or kind == QEvent.MouseButtonRelease
        trace_recorder = self._mouse_trace_recorder
        # Pre-start movement and ordinary presses stay gated. Only a candidate
        # action needs geometry/time before synchronous engine/Replay processing.
        trace_position = None
        if (trace_recorder.eligible and not trace_recorder.frozen
                and (trace_recorder.started or action_observation)):
            trace_position = self._mouse_trace_position(event)
        trace_observed_ns = None
        if trace_position is not None:
            if action_observation:
                trace_observed_ns = trace_recorder.observation_time_ns()
            else:
                trace_recorder.record_position(*trace_position, self._cell_size)
        if action_observation:
            trace_event_count = len(self._replay_recorder.events)
            trace_cell_size = self._cell_size

        if kind == QEvent.MouseMove:
            if not self._mouse_buttons:
                return
            if buttons != self._mouse_buttons:
                self._invalidate_mouse_input()
                return
            self._mouse_position = event.globalPos()
        else:
            self._mouse_position = event.globalPos()
            target = self._cell_at_mouse_position(self._mouse_position)
            if press:
                self._mouse_buttons = buttons
                if button == Qt.LeftButton:
                    self._mouse_left_suppressed = set()
                    self._mouse_left_consumed = False
                # One overlap, independent of origins and any prior overlap.
                self._mouse_both = (self._chord_mode == ChordMode.BOTH_CLICK
                                    and buttons == (Qt.LeftButton | Qt.RightButton))
                if right_action and target is not None:
                    suppressed = self._mouse_left_suppressed
                    was_flagged = (self.engine.get_observation()[target.y][target.x]
                                   == CellState.FLAGGED)
                    self._emit_mouse_action(target, "right_clicked", trace_position, trace_observed_ns)
                    if (self._mouse_buttons & Qt.LeftButton
                            and self._mouse_left_suppressed is suppressed):
                        # A synchronous callback can reset/rebuild the board.
                        is_flagged = (self.engine.get_observation()[target.y][target.x]
                                      == CellState.FLAGGED)
                        if is_flagged and not was_flagged:
                            suppressed.add((target.x, target.y))
                        elif not is_flagged:
                            suppressed.discard((target.x, target.y))
            else:
                both = self._mouse_both
                suppress_left = (self._mouse_left_consumed
                                 or (target is not None
                                     and (target.x, target.y) in self._mouse_left_suppressed
                                     and self.engine.get_observation()[target.y][target.x]
                                     == CellState.FLAGGED))
                self._mouse_buttons = buttons
                # Consume even an outside release before dispatch. A remaining
                # LEFT release is inert, but a new RIGHT press can re-arm BOTH.
                self._mouse_both = False
                if both:
                    self._mouse_left_consumed = bool(buttons & Qt.LeftButton)
                if button == Qt.LeftButton:
                    self._mouse_left_suppressed = set()
                    self._mouse_left_consumed = False
                self._set_mouse_preview(set())
                if not buttons:
                    self._invalidate_mouse_input()
                if target is not None:
                    if both:
                        self._emit_mouse_action(target, "both_clicked", trace_position, trace_observed_ns)
                    elif button == Qt.LeftButton and not suppress_left:
                        self._emit_mouse_action(target, "left_clicked", trace_position, trace_observed_ns)
                # RIGHT release never dispatches a standalone FLAG.

        if (action_observation and trace_position is not None
                and trace_recorder is self._mouse_trace_recorder
                and len(self._replay_recorder.events) == trace_event_count
                and self._buttons.get((source.x, source.y)) is source
                and self._cell_size == trace_cell_size
                and self._mouse_trace_position(event) == trace_position):
            # Committed actions already supplied this observation. An ignored
            # press/release remains a sample unless dispatch changed its context.
            trace_recorder.record_position(*trace_position, trace_cell_size,
                                           observed_ns=trace_observed_ns)
        self._update_mouse_preview()

        self._update_policy_controls()

        # A complete gesture can resume Simple with its fresh post-input result.
        # Holding a button never starts a timer or consumes the next decision.
        if (not self._mouse_buttons and self._live_policy == POLICY_SIMPLE
                and self.simple_auto_checkbox.isChecked() and self.analysis_checkbox.isChecked()
                and self._analysis_result is not None and not self._simple_auto_pending):
            self._schedule_simple_auto_step()

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

        if self._is_revealed_number(x, y):
            if self._chord_mode == ChordMode.LEFT_CLICK:
                action = Action.CHORD
            elif self._chord_mode == ChordMode.BOTH_CLICK:
                action = Action.OPEN
            else:
                return
        else:
            action = Action.OPEN
        self._apply_live_action(x, y, action)

    def on_right_click(self, x: int, y: int):
        if self._replay_mode:
            return
        if self._game_over:
            return
        self._apply_live_action(x, y, Action.FLAG)

    def on_both_click(self, x: int, y: int):
        if self._replay_mode:
            return
        if self._game_over:
            return
        if self._chord_mode == ChordMode.DISABLED:
            return
        self._apply_live_action(x, y, Action.CHORD)

    def _apply_live_action(self, x, y, action, *, auto_observation=None):
        """One physical action, one event in the existing live recorder."""
        if self._live_closing or self._replay_mode or self.engine.status != GameStatus.PLAYING:
            return None
        if auto_observation is None:
            self._reset_simple_preparation()
            self._retire_v1_for_manual("수동 입력으로 인계")
            if self._live_policy in (POLICY_V1, POLICY_K, POLICY_K_LC0, POLICY_K_LC1):
                blocked = self.allow_guess_checkbox.blockSignals(True)
                self.allow_guess_checkbox.setChecked(False)
                self.allow_guess_checkbox.blockSignals(blocked)
        self._cancel_simple_auto_step()
        observation = self._mouse_trace_observation
        self._mouse_trace_observation = None
        before = self.engine.get_counter_snapshot()
        before_status = self.engine.status
        before_placement = self.engine.get_board_snapshot().mines_placed if auto_observation is not None else None
        self._live_action_count += 1
        self._live_fresh_reset = False
        self._v1_cursor = (x, y)  # Actual input target, including wasted inputs.
        try:
            _, _, _, _, info = self.engine.step(x, y, action)
        except Exception:
            self._live_input_uncertain = True
            if auto_observation is not None:
                try:
                    unchanged = (self.engine.status == before_status
                                 and self.engine.get_counter_snapshot() == before
                                 and tuple(tuple(row) for row in self.engine.get_observation())
                                 == tuple(tuple(row) for row in auto_observation)
                                 and self.engine.get_board_snapshot().mines_placed == before_placement)
                except Exception:
                    unchanged = False
                if not unchanged:
                    self._mark_automated_recording()
            raise
        status_after = self.engine.status
        after = self.engine.get_counter_snapshot()
        committed = (after["active_clicks"] + after["wasted_clicks"]
                     > before["active_clicks"] + before["wasted_clicks"])
        if committed:
            self.auto_cursor_overlay.set_actual((x, y))
        if committed and auto_observation is not None:
            self._mark_automated_recording()
        elif (committed and observation is not None and observation[0] is self._mouse_trace_recorder
              and action in (Action.OPEN, Action.FLAG) and not self._mouse_trace_recording_locked):
            self._lock_mouse_trace_recording()
            if not self._mouse_trace_recording_enabled:
                self._mouse_trace_recorder.invalidate()
        self._ensure_zini_metric_job()
        if action in (Action.OPEN, Action.FLAG):
            self._start_timer()
        event_index = self._record_replay_event(x, y, action)
        if auto_observation is not None and event_index is not None:
            self._mark_automated_recording()
        if committed and event_index is None:
            self._live_input_uncertain = True
        if auto_observation is not None and (committed or event_index is not None):
            self.live_auto_totals["auto_inputs"] += 1
            if self._live_policy == POLICY_SIMPLE:
                self.live_auto_totals["simple_inputs"] += 1
        self.live_input_records.append({
            "game_id": self._live_game_id,
            "run_id": self._live_run_id if self._v1_owned else None,
            "board_generation": self._live_board_generation,
            "input_revision": self._live_action_count, "event_index": event_index,
            "action": action.name, "x": x, "y": y,
            "automatic": auto_observation is not None, "status": status_after.name,
        })
        if committed and auto_observation is None and observation is not None:
            recorder, position, cell_size, observed_ns = observation
            if (recorder is self._mouse_trace_recorder
                    and (recorder.started or action in (Action.OPEN, Action.FLAG))):
                if event_index is None:
                    # A committed action missing from the authoritative Replay
                    # stream makes the entire human trace unusable this game.
                    recorder.invalidate()
                else:
                    recorder.record_action(*position, cell_size, event_index, observed_ns=observed_ns)
        if status_after != GameStatus.PLAYING:
            self._mouse_trace_recorder.freeze()
        self._refresh_live_board(info, auto_observation=auto_observation)
        return event_index

    def _mark_automated_recording(self):
        self._replay_recorder.source_type = SOURCE_ALGORITHM
        self._mouse_trace_recorder.invalidate()
        self._lock_mouse_trace_recording()
        self._update_same_board_comparison_action()

    def on_reset(self):
        if self._replay_mode or self._live_closing:
            return
        if self.live_policy_combo.currentData() not in (POLICY_SIMPLE, POLICY_V1, POLICY_K, POLICY_K_LC0, POLICY_K_LC1):
            self._stop_simple_auto()
            self._clear_live_analysis("선택한 정책은 이번 단계에서 지원하지 않습니다.")
            return
        self._invalidate_v1_run("새 게임")
        self._invalidate_mouse_input()
        self._stop_simple_auto()
        self._clear_live_analysis()
        self._reset_counter_metrics_for_board_change()
        self.engine.reset()
        self._prepare_live_policy_game()
        self._game_over = False
        self.reset_button.setText("🙂")
        self._reset_timer()
        self._reset_replay_recorder()
        self._refresh_live_board()
        # 리셋 직후에는 PLAYING 상태이므로 마스킹/초기 값이 표시된다.
        self._update_statistics_panel(self.engine.get_stats())
        self._update_same_board_comparison_action()

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
    # Live analysis and single-action auto control.
    # ------------------------------------------------------------------
    def _create_v1_job(self):
        job = LivePolicyJob(self)
        job.proposal_ready.connect(self._on_v1_proposal)
        job.admitted.connect(self._on_k_admitted)
        job.bootstrapped.connect(self._on_k_bootstrapped)
        job.acknowledged.connect(self._on_v1_acknowledged)
        job.finished.connect(self._on_v1_finished)
        return job

    def _restore_after_auxiliary_close_refusal(self):
        # Our owner was successfully reaped; an unrelated auxiliary refused close.
        if self._v1_job.state == "closed":
            prior_records = list(self._v1_job.records)
            self._v1_job.deleteLater()
            self._v1_job = self._create_v1_job()
            self._v1_job.records.extend(prior_records)
            self._live_closing = False
            self._live_close_error = None
            self._update_policy_controls()

    def _v1_supported(self):
        return (supports_v1_board(self.engine.width, self.engine.height, self.engine.num_mines)
                and self.difficulty_combo.currentText() != "커스텀")

    def _v1_board_locked(self):
        # Ownership never locks ordinary board gestures. Errors block Auto only.
        return False

    @staticmethod
    def _empty_live_auto_totals():
        return {"auto_inputs": 0, "simple_inputs": 0, "v1_inputs": 0,
                "preparation_inputs": 0, "v1_modeled_us": 0,
                "preparation_modeled_us": 0, "modeled_us": 0,
                "preparation_unmodeled_inputs": 0,
                "k_inputs": 0, "k_modeled_us": 0}

    def _k_fresh_start(self):
        return (self._k_reset_ready and not self._k_retired and self._live_fresh_reset and self._live_action_count == 0
                and self._v1_cursor == (0, 0) and self.engine.status == GameStatus.PLAYING
                and is_all_hidden(self.engine.get_observation())
                and not self.engine.get_board_snapshot().mines_placed)

    def _known_live_history(self):
        """Attest this UI's input ledger, never reconstruct history from a grid."""
        if not self._live_history_known or self._live_input_uncertain:
            return False
        count = self._live_action_count
        counters = self.engine.get_counter_snapshot()
        if (type(count) is not int or count < 0 or len(self.live_input_records) != count
                or counters['active_clicks'] + counters['wasted_clicks'] != count):
            return False
        if count == 0:
            return not self._replay_recorder.events and self._v1_cursor == (0, 0)
        last = self.live_input_records[-1]
        return (last['game_id'] == self._live_game_id and last['input_revision'] == count
                and (last['x'], last['y']) == self._v1_cursor
                and last['event_index'] is not None
                and last['event_index'] == len(self._replay_recorder.events) - 1)

    def _k_start_block_reason(self):
        if self._k_retired or self._v1_manual_only or self._live_input_uncertain:
            return self._live_failure_text()
        if self._k_retiring is not None:
            return "수동 인계 정리 중 · 이전 입력 확인 후 다시 시작하세요."
        if self.engine.status != GameStatus.PLAYING:
            return "게임이 종료되었습니다."
        if not self._v1_supported():
            return "초급·중급·상급만 지원합니다. 커스텀 보드는 지원하지 않습니다."
        if not self._known_live_history():
            return "실제 입력 이력·기록을 확인할 수 없습니다. 새 게임이 필요합니다."
        if self._live_action_count == 0 and not self._k_fresh_start():
            return f"{k_live.policy_label(self._live_policy)} 첫 시작은 선택 정책으로 새 게임을 눌러 주세요."
        return None

    def _on_live_policy_changed(self, *_args):
        selected = self.live_policy_combo.currentData()
        if selected not in (POLICY_SIMPLE, POLICY_V1, POLICY_K, POLICY_K_LC0, POLICY_K_LC1):
            blocked = self.live_policy_combo.blockSignals(True)
            self.live_policy_combo.setCurrentIndex(self.live_policy_combo.findData(self._live_policy))
            self.live_policy_combo.blockSignals(blocked)
            return
        if selected != self._live_policy:
            self._invalidate_v1_run("Auto 정책 변경", drain_ack=True)
            self._live_policy = selected
            self._v1_status = "수동 · 다음 Auto ON에 현재 판 인수"
            self._clear_live_analysis("정책 선택 완료 · Auto OFF")
        self._update_policy_controls()

    def _update_policy_controls(self, *_args):
        if not hasattr(self, "live_policy_combo") or not hasattr(self, "simple_auto_checkbox"):
            return
        if hasattr(self, "auto_cursor_overlay"):
            self.auto_cursor_overlay.set_available(
                self._v1_owned and self._live_policy in (POLICY_V1, POLICY_K, POLICY_K_LC0, POLICY_K_LC1)
                and not self._replay_mode and not self._live_closing
                and not self._live_input_uncertain and not self._v1_manual_only
                and not (k_live.is_k_policy(self._live_policy) and self._k_retired))
            self.auto_cursor_checkbox.setEnabled(
                self._live_policy in (POLICY_V1, POLICY_K, POLICY_K_LC0, POLICY_K_LC1) and not self._replay_mode and not self._live_closing)
        live_available = not self._replay_mode and not self._live_closing
        self.reset_button.setEnabled(live_available)
        self.difficulty_combo.setEnabled(live_available)
        self.live_policy_combo.setEnabled(live_available)
        self.live_policy_new_game_button.setEnabled(live_available)
        self.simple_auto_interval_spin.setEnabled(live_available)
        if self._live_closing:
            self.allow_guess_checkbox.setEnabled(False)
        for control in (self.live_policy_label, self.live_policy_combo,
                        self.live_policy_new_game_button, self.simple_auto_checkbox,
                        self.auto_interval_label, self.simple_auto_interval_spin,
                        self.allow_guess_checkbox):
            control.setVisible(not self._replay_mode)
        self.analysis_checkbox.setText("참고 분석 표시" if self._replay_mode else "분석 표시")
        self.analyze_button.setText("참고 분석" if self._replay_mode else "현재 상태 분석")
        self.analysis_checkbox.setToolTip(
            "Replay 현재 보드의 참고 분석입니다. 저장된 플레이 정책을 나타내지 않습니다."
            if self._replay_mode else "현재 보드를 분석하고 사용자 액션 후 자동 갱신")
        self.analyze_button.setToolTip(
            "참고 분석 표시가 켜져 있을 때 현재 보드를 Stage2 Simple로 분석합니다."
            if self._replay_mode else "한 번 분석하여 표시 (추천 액션은 실행하지 않음)")
        self.simple_auto_checkbox.setToolTip(
            "Auto OFF는 추천·추측 선택을 보관하는 일시정지입니다. 보드를 클릭하면 수동으로 전환하며 추측 선택을 해제합니다.")
        if self._live_close_error is not None:
            # Presentation only: shutdown's closing/ownership/failure state stays latched.
            self.simple_auto_checkbox.setEnabled(False)
            self.analyze_button.setEnabled(self._replay_mode)
            self.live_policy_status_label.setText(
                "종료 정리에 실패했습니다. 새 게임·자동 진행을 사용할 수 없습니다.\n"
                f"원인: {self._live_close_error}")
            return
        if self._replay_mode:
            source = self._replay_data.source_type if self._replay_data is not None else None
            recorded = ("있음" if source in (SOURCE_ALGORITHM, SOURCE_AI)
                        else "없음" if source == SOURCE_HUMAN else "확인 불가")
            self.live_policy_status_label.setText(f"알고리즘 사용 기록: {recorded}")
            self.live_policy_status_label.setToolTip(
                "저장된 사용 기록만 표시합니다. 외부·옛 파일의 실제 알고리즘 사용 여부나 정책을 검증한 정보는 아닙니다.")
            return
        self.live_policy_status_label.setToolTip("")
        cleanup_ready = self._k_retiring is None and (self._v1_owned or self._v1_job.state == "idle")
        runnable = (not self._live_closing and not self._live_input_uncertain
                    and self.engine.status == GameStatus.PLAYING
                    and cleanup_ready)
        if self._live_policy == POLICY_SIMPLE:
            text = "현재: Stage2 Simple"
            if self._v1_job.state == "blocked":
                text += " | 수동 가능 · 이전 Auto 정리 실패"
            elif not cleanup_ready:
                text += " | 수동 가능 · 이전 Auto 정리 중"
        else:
            label = f"{k_live.policy_label(self._live_policy)} (실험적)" if k_live.is_k_policy(self._live_policy) else "Stage3 V1"
            text = f"현재: {label} | " + self._v1_status
            if self._v1_job.state == "blocked":
                text += " | 수동 가능 · Auto 정리 실패"
            elif not cleanup_ready:
                text += " | 수동 가능 · 이전 Auto 정리 중"
            if not self._v1_supported():
                text = f"현재: {label} | 초급·중급·상급 지원 (커스텀 미지원)"
            runnable = (runnable and self._v1_supported() and not self._v1_manual_only
                        and not self._live_input_uncertain and self._v1_job.state != "blocked")
            if k_live.is_k_policy(self._live_policy) and not self._v1_owned:
                reason = self._k_start_block_reason()
                if reason:
                    text = f"현재: {label} | " + reason
                    runnable = False
                elif any(v == CellState.FLAGGED for row in self.engine.get_observation() for v in row):
                    text = f"현재: {label} | 깃발 확인/정리 후 현재 판 계속"
                if not cleanup_ready:
                    text += " · 이전 worker 정리 중/실패"
        if self._live_first_failure is not None or self._live_input_uncertain or self._v1_manual_only:
            text = self._live_failure_text()
            runnable = False
        elif self._k_retiring is not None:
            text = "수동 인계 정리 중 · 이전 입력 확인/worker 정리 대기"
        elif self.engine.status != GameStatus.PLAYING:
            text = f"게임 종료 ({self.engine.status.name}) | {self._v1_status}"
        self.simple_auto_checkbox.setEnabled(runnable)
        self.analyze_button.setEnabled(runnable)
        self.live_policy_status_label.setText(text)
        self.simple_auto_checkbox.setText(
            f"{k_live.policy_label(self._live_policy)} 자동 진행" if k_live.is_k_policy(self._live_policy) else
            "V1 자동 진행" if self._live_policy == POLICY_V1 else "확정 수 자동 진행")

    def _prepare_live_policy_game(self):
        # A new Live board is manual with fresh guess permission required.
        for checkbox in (self.simple_auto_checkbox, self.allow_guess_checkbox):
            blocked = checkbox.blockSignals(True)
            checkbox.setChecked(False)
            checkbox.blockSignals(blocked)
        self.allow_guess_checkbox.setEnabled(False)
        selected = self.live_policy_combo.currentData()
        if selected not in (POLICY_SIMPLE, POLICY_V1, POLICY_K, POLICY_K_LC0, POLICY_K_LC1):
            selected = self._live_policy
            blocked = self.live_policy_combo.blockSignals(True)
            self.live_policy_combo.setCurrentIndex(self.live_policy_combo.findData(selected))
            self.live_policy_combo.blockSignals(blocked)
        self._live_policy = selected
        self._live_run_id = uuid4().hex
        self._live_game_id = uuid4().hex
        self._live_action_count = 0
        self._live_fresh_reset = True
        self._live_history_known = True
        self._live_input_uncertain = False
        self._live_first_failure = None
        self._k_ack_receipt = None
        self._k_retiring = None
        self._v1_cursor = (0, 0)
        self.auto_cursor_overlay.set_actual((0, 0))
        self.auto_cursor_overlay.clear()
        self._v1_input_seq = 0
        self._v1_entry_mode = CANONICAL_NEW
        self._v1_phase = PHASE_V1
        self._v1_initial_flag_count = self._v1_review_inputs = 0
        self._v1_expected_ack = None
        self._v1_pending = None
        self._v1_owned = False
        self._v1_manual_only = False
        self._k_retired = False
        self._k_start_input_revision = 0
        self._k_phase = (k_live.normal_phase(self._live_policy)
                             if k_live.is_k_policy(self._live_policy) else k_live.PHASE_K)
        self._k_preparation_seq = 0
        self._k_normal_start = None
        self._k_bootstrap = None
        self._k_base_m = ()
        self._k_m_revision = 0
        self._k_validation_nonce = None
        self._v1_display_requested = False
        self._v1_status = "새 게임 · 수동 · Auto OFF"
        self._k_reset_ready = True
        self.live_action_records = []
        self.live_input_records = []
        self.live_auto_totals = self._empty_live_auto_totals()
        self._update_policy_controls()

    def _invalidate_v1_run(self, reason, *, cancel=True, drain_ack=False):
        # Revoke input permission immediately. Only the sealed completed input
        # can outlive this owner; its ACK never authorizes another NEXT.
        self._reset_simple_preparation()
        if drain_ack and self._k_retiring is None and self._k_ack_receipt is not None:
            try:
                self._verify_k_receipt(self._k_ack_receipt, self._v1_expected_ack)
                self._k_retiring = self._k_ack_receipt
            except Exception as exc:
                self._record_live_failure(str(exc), stage="handoff")
        waiting = drain_ack and self._k_retiring is not None
        if not waiting:
            if self._v1_expected_ack is not None and k_live.is_k_policy(self._live_policy):
                self._record_live_failure("이전 실제 입력의 ACK를 확인하지 못했습니다.", stage="ACK")
            self._k_retiring = None
        self._set_auto_off(clear_guess=True)
        self._live_board_generation += 1
        self._cancel_simple_auto_step()
        self._v1_pending = None
        self._v1_expected_ack = None
        self._k_ack_receipt = None
        self._v1_owned = False
        self.auto_cursor_overlay.clear()
        self._v1_display_requested = False
        self._clear_live_analysis(reason)
        for record in reversed(self.live_owner_records):
            if record["run_id"] == self._live_run_id and record.get("end_reason") is None:
                record.update(end_reason=reason, end_revision=self._live_action_count,
                              end_event_index=len(self._replay_recorder.events),
                              end_cursor=self._v1_cursor)
                break
        self._k_base_m = ()
        self._k_m_revision = 0
        self._k_start_input_revision = 0
        self._k_phase = (k_live.normal_phase(self._live_policy)
                             if k_live.is_k_policy(self._live_policy) else k_live.PHASE_K)
        self._k_preparation_seq = 0
        self._k_normal_start = None
        self._k_bootstrap = None
        if self._live_policy in (POLICY_V1, POLICY_K, POLICY_K_LC0, POLICY_K_LC1):
            self._v1_status = reason
        if cancel and not waiting and self._v1_job.active_run_id is not None:
            self._v1_job.cancel(reason)

    def _retire_v1_for_manual(self, reason):
        if self._replay_mode:
            return
        if self._live_policy == POLICY_SIMPLE:
            self._set_auto_off(clear_guess=True)
            self._clear_live_analysis("수동 플레이")
            return
        if not (self._v1_owned or self._v1_pending is not None or self.simple_auto_checkbox.isChecked()):
            self._set_auto_off(clear_guess=True)
            return
        self._invalidate_v1_run(reason, drain_ack=True)
        self._clear_live_analysis(f"수동 플레이 · 정리 후 현재 판을 {k_live.policy_label(self._live_policy)}로 인수" if k_live.is_k_policy(self._live_policy)
                                  else "수동 플레이 · 정리 후 Auto ON으로 다시 인수")
        self._update_policy_controls()

    def _v1_snapshot(self):
        if k_live.is_k_policy(self._live_policy):
            return k_live.make_snapshot(
                run_id=self._live_run_id, board_generation=self._live_board_generation,
                input_seq=self._v1_input_seq, width=self.engine.width, height=self.engine.height,
                num_mines=self.engine.num_mines, observation=self.engine.get_observation(),
                cursor=self._v1_cursor, input_revision=self._live_action_count,
                base_m_revision=self._k_m_revision, base_m=self._k_base_m,
                entry_mode=self._v1_entry_mode, start_input_revision=self._k_start_input_revision,
                phase=self._k_phase, preparation_seq=self._k_preparation_seq,
                k_start_input_revision=self._k_normal_start, bootstrap=self._k_bootstrap,
                game_id=self._live_game_id, policy_id=self._live_policy,
                definition=k_live.definition_for_entry(self._v1_entry_mode, self._live_policy), status=self.engine.status.name)
        return make_snapshot(
            run_id=self._live_run_id, board_generation=self._live_board_generation,
            input_seq=self._v1_input_seq, width=self.engine.width, height=self.engine.height,
            num_mines=self.engine.num_mines, observation=self.engine.get_observation(),
            cursor=self._v1_cursor, policy_id=POLICY_V1, status=self.engine.status.name,
            entry_mode=self._v1_entry_mode, input_revision=self._live_action_count,
            phase=self._v1_phase, initial_flag_count=self._v1_initial_flag_count,
            review_inputs=self._v1_review_inputs,
        )

    def _admit_live_proposal(self, proposal):
        if k_live.is_k_policy(self._live_policy):
            return k_live.admit_proposal(proposal, self._v1_snapshot())
        return admit_proposal(proposal, self._v1_snapshot())

    def _fail_v1(self, message):
        self._record_live_failure(message)
        self._invalidate_v1_run("중단 · 새 게임이 필요합니다")
        if k_live.is_k_policy(self._live_policy):
            self._k_retired = True
        self._v1_manual_only = True  # Unexpected failure, never normal handoff.
        self._live_input_uncertain = True
        self._set_auto_off(clear_guess=True)
        label = k_live.policy_label(self._live_policy) if k_live.is_k_policy(self._live_policy) else "V1"
        self._clear_live_analysis(f"{label} 자동 진행 중단 - {message}")
        self._update_policy_controls()

    def _live_failure_text(self):
        cause = (self._live_first_failure or {}).get('cause', '실제 입력·기록을 확인할 수 없습니다.')
        terminal = f"{self._v1_status} | " if self.engine.status != GameStatus.PLAYING else ""
        return f"{terminal}자동 진행 차단: {cause} · 새 게임이 필요합니다. 수동 플레이는 가능합니다."

    def _record_live_failure(self, message, *, stage=None):
        if self._live_first_failure is None:
            failure = dict(game_id=self._live_game_id, run_id=self._live_run_id,
                           input_revision=self._live_action_count, cause=str(message),
                           stage=stage or self._v1_job.state,
                           ack_pending=self._v1_expected_ack is not None or self._k_retiring is not None,
                           cleanup_state=self._v1_job.state)
            self._live_first_failure = failure
            self.live_failure_records.append(failure)
            for owner in reversed(self.live_owner_records):
                if owner['run_id'] == self._live_run_id:
                    owner['first_failure'] = dict(failure)
                    break
        self._live_input_uncertain = True
        self._v1_manual_only = True
        if k_live.is_k_policy(self._live_policy) or self._k_retiring is not None:
            self._k_retired = True

    def _seal_k_receipt(self, ack, action):
        if not self._known_live_history():
            raise ValueError("K 실제 입력 이력을 확인할 수 없습니다.")
        return _KInputReceipt(ack, self._live_game_id,
                              tuple(tuple(sorted(row.items())) for row in self.live_input_records),
                              tuple(self._replay_recorder.events),
                              tuple(action.get(key) for key in _K_RECEIPT_FIELDS))

    def _verify_k_receipt(self, receipt, ack):
        if type(receipt) is not _KInputReceipt or ack != receipt.ack or receipt.acknowledged:
            raise ValueError("K ACK가 원 입력과 다르거나 중복되었습니다.")
        ack.__post_init__()
        k_live.next_snapshot(ack.permit.proposal, ack)
        matches = [row for row in self.live_action_records
                   if row.get('run_id') == ack.run_id and row.get('token') == ack.token]
        if (receipt.game_id != self._live_game_id or len(matches) != 1
                or tuple(matches[0].get(key) for key in _K_RECEIPT_FIELDS) != receipt.action
                or tuple(tuple(sorted(row.items())) for row in self.live_input_records[:len(receipt.history)]) != receipt.history
                or tuple(self._replay_recorder.events[:len(receipt.events)]) != receipt.events
                or not self._known_live_history()):
            raise ValueError("K 원 입력/Replay 이력이 달라졌습니다.")
        return matches[0]

    def _show_v1_pending(self):
        proposal = self._v1_pending
        if proposal is None:
            return
        self._analysis_result = (present_k_proposal(proposal) if k_live.is_k_policy(self._live_policy)
                                 else present_v1_proposal(proposal))
        self._analysis_observation = proposal.snapshot.observation
        self._analysis_first_click = proposal.kind == "initial"
        self.analysis_status_label.setText(self._analysis_result.status_text)
        preparing = (proposal.is_preparation if k_live.is_k_policy(self._live_policy)
                     else proposal.is_flag_review)
        self._remember_live_certainty(preparing=preparing)
        self._render_live_analysis()
        self._schedule_v1_step()

    def _analyze_v1_current(self):
        if (self._live_closing or self._replay_mode or self._v1_manual_only
                or self._live_input_uncertain or self.engine.status != GameStatus.PLAYING):
            self._stop_simple_auto()
            return
        if self._mouse_buttons:
            self._stop_simple_auto()
            self._v1_status = "마우스 버튼을 놓은 뒤 Auto 또는 분석을 시작하세요"
            self._update_policy_controls()
            return
        if not self._v1_supported():
            self._stop_simple_auto()
            self._v1_status = "지원하지 않는 보드"
            self._update_policy_controls()
            return
        try:
            if self._v1_pending is not None:
                self._admit_live_proposal(self._v1_pending)
                self._show_v1_pending()
                self._v1_display_requested = False
                return
            if self._v1_owned:
                if self._v1_job.state == "ready":
                    self._v1_job.request(self._v1_snapshot())
                    self._v1_status = "계산 중"
                self._update_policy_controls()
                return
            if self._v1_job.state != "idle":
                self._stop_simple_auto()
                self._v1_status = "이전 worker 정리 중 · 완료 후 다시 시작하세요"
                self._update_policy_controls()
                return
            if k_live.is_k_policy(self._live_policy):
                reason = self._k_start_block_reason()
                if reason:
                    self._stop_simple_auto()
                    self._v1_status = reason
                    self._clear_live_analysis(reason)
                    self._update_policy_controls()
                    return
            observation = self.engine.get_observation()
            pristine = (self._live_fresh_reset and self._live_action_count == 0
                        and is_all_hidden(observation)
                        and not self.engine.get_board_snapshot().mines_placed
                        and self._v1_cursor == (0, 0))
            if self._live_action_count == 0 and not pristine:
                raise ValueError("마지막 실제 입력을 확인할 수 없습니다. 새 게임이 필요합니다.")
            self._live_run_id = uuid4().hex
            self._v1_input_seq = self._v1_review_inputs = 0
            self._v1_expected_ack = None
            self._v1_entry_mode = CANONICAL_NEW if pristine else ADOPT_CURRENT
            self._k_start_input_revision = self._live_action_count
            self._k_base_m = ()
            self._k_m_revision = 0
            self._v1_initial_flag_count = sum(value == CellState.FLAGGED
                                              for row in observation for value in row)
            self._k_phase = (k_live.normal_phase(self._live_policy)
                             if k_live.is_k_policy(self._live_policy) else k_live.PHASE_K)
            self._k_preparation_seq = 0
            self._k_normal_start = None
            self._k_bootstrap = None
            if k_live.is_k_policy(self._live_policy) and self._v1_initial_flag_count:
                self._v1_entry_mode = k_live.FLAG_ADOPT
                self._k_phase = k_live.PHASE_BOOTSTRAP
            self._v1_phase = PHASE_FLAG_REVIEW if self._v1_initial_flag_count else PHASE_V1
            snapshot = self._v1_snapshot()
            self.live_owner_records.append({
                "game_id": self._live_game_id, "run_id": self._live_run_id,
                "policy_id": self._live_policy,
                "definition": snapshot.definition if k_live.is_k_policy(self._live_policy) else "STAGE3_V1",
                "board_generation": self._live_board_generation,
                "entry_mode": self._v1_entry_mode,
                "phase": self._k_phase if k_live.is_k_policy(self._live_policy) else self._v1_phase,
                "start_revision": self._live_action_count,
                "start_input_revision": self._live_action_count,
                "start_event_index": len(self._replay_recorder.events),
                "cursor": self._v1_cursor, "initial_flag_count": self._v1_initial_flag_count,
                "end_reason": None, "cleanup": None, "review": None,
                "k_actions": [],
                "preparation_input_count": 0, "k_input_count": 0, "k_ack_count": 0,
            })
            self._v1_owned = True
            self._v1_job.start(snapshot)
            self._v1_status = ("깃발 확인/정리 중" if self._v1_initial_flag_count else "계산 중")
            if self._v1_initial_flag_count:
                self._clear_live_analysis("깃발 확인/정리 중 · 미확인 깃발은 실제 지뢰여도 해제될 수 있습니다.")
            self._update_policy_controls()
        except Exception as exc:
            self._fail_v1(str(exc))

    def _record_k_policy_start(self):
        if (not k_live.is_k_policy(self._live_policy)
                or self._k_phase != k_live.normal_phase(self._live_policy)
                or self._v1_entry_mode != k_live.FLAG_ADOPT):
            return
        for owner in reversed(self.live_owner_records):
            if owner['run_id'] == self._live_run_id and 'k_start_revision' not in owner:
                owner.update(k_start_revision=self._live_action_count,
                             k_start_event_index=len(self._replay_recorder.events), k_start_cursor=self._v1_cursor)
                break

    def _on_k_bootstrapped(self, exchange):
        if (not k_live.is_k_policy(self._live_policy) or self._live_closing or self._replay_mode
                or not self._v1_owned or self._k_retired):
            return
        try:
            start, following = exchange
            if start.run_id != self._live_run_id:
                return
            if (self._mouse_buttons or not self._known_live_history() or not self._v1_supported()
                    or start != self._v1_snapshot() or following != k_live.after_bootstrap(start, following.bootstrap)):
                raise ValueError("깃발 확인 뒤 현재 판/입력 이력이 달라졌습니다.")
            self._k_bootstrap = following.bootstrap
            self._k_base_m, self._k_m_revision = following.base_m, following.base_m_revision
            self._k_normal_start, self._k_phase = following.k_start_input_revision, following.phase
            for owner in reversed(self.live_owner_records):
                if owner['run_id'] == self._live_run_id:
                    owner.update(bootstrap=k_live.to_dict(following.bootstrap),
                                 planned_k_start_revision=self._k_normal_start)
                    break
            self._record_k_policy_start()
            # This is still the explicit analysis request, not an actual input.
            self._v1_job.request(self._v1_snapshot())
            self._v1_status = "깃발 확인/정리 후 현재 판 계속"
            self._update_policy_controls()
        except Exception as exc:
            self._fail_v1(str(exc))

    def _on_v1_proposal(self, proposal):
        if (self._live_closing or self._replay_mode or not self._v1_owned
                or self._live_policy not in (POLICY_V1, POLICY_K, POLICY_K_LC0, POLICY_K_LC1)
                or proposal.snapshot.run_id != self._live_run_id):
            return
        try:
            self._admit_live_proposal(proposal)
            if self._v1_pending is not None:
                raise ValueError("중복된 V1 추천입니다.")
            self._v1_pending = proposal
            if self._live_policy == POLICY_V1 and proposal.review is not None:
                for record in reversed(self.live_owner_records):
                    if record["run_id"] == self._live_run_id:
                        record["review"] = report_to_dict(proposal.review)
                        break
            preparing = (proposal.is_preparation if k_live.is_k_policy(self._live_policy) else proposal.is_flag_review)
            self._v1_status = ("깃발 확인/정리 · 준비 대기" if preparing else
                               "입력 대기" if self.simple_auto_checkbox.isChecked() else "일시정지 · 추천 보관")
            if self.analysis_checkbox.isChecked() or self._v1_display_requested:
                self._show_v1_pending()
                self._v1_display_requested = False
            self._update_policy_controls()
        except Exception as exc:
            self._fail_v1(str(exc))

    def _schedule_v1_step(self):
        self._cancel_simple_auto_step()
        if (self._v1_pending is None or not self._v1_owned or self._live_closing
                or self._replay_mode or self.engine.status != GameStatus.PLAYING
                or self._mouse_buttons
                or not self.simple_auto_checkbox.isChecked() or not self.analysis_checkbox.isChecked()):
            return
        try:
            self._admit_live_proposal(self._v1_pending)
            if self._v1_pending.is_guess and not self.allow_guess_checkbox.isChecked():
                self._v1_status = "추측 대기 · 추측 허용 꺼짐"
                if self._analysis_result is not None:
                    self.analysis_status_label.setText(self._analysis_result.status_text + " | 추측 대기")
                self._update_policy_controls()
                return
            if k_live.is_k_policy(self._live_policy) and self._v1_job.state != "pending":
                return  # Drain an outstanding VALIDATE before reserving another.
            preparing = (self._v1_pending.is_preparation if k_live.is_k_policy(self._live_policy)
                         else self._v1_pending.is_flag_review)
            self._v1_status = "깃발 확인/정리 · 준비 입력 대기" if preparing else "입력 대기"
            reservation = (self._live_run_id, self._live_board_generation,
                           self._live_action_count, self._v1_pending.token, self._v1_timer_nonce)
            self._v1_timer_reservation = reservation
            self._connect_auto_timeout(lambda reservation=reservation: self._on_v1_auto_timeout(reservation))
            self._simple_auto_pending = True
            self._simple_auto_timer.start()
            self.auto_cursor_overlay.reserve(
                reservation, self._v1_cursor, (self._v1_pending.x, self._v1_pending.y),
                self._simple_auto_timer.interval())
            self._update_policy_controls()
        except Exception as exc:
            self._fail_v1(str(exc))

    def _on_v1_auto_timeout(self, reservation=None):
        # A queued callback belongs only to its original reservation. Reject it
        # before touching a newer timer or pending proposal.
        if reservation is None or reservation != self._v1_timer_reservation:
            return
        scheduled = self._simple_auto_pending
        self._cancel_simple_auto_step()
        if (not scheduled or self._live_closing or self._replay_mode or not self._v1_owned
                or self._mouse_buttons
                or not self.simple_auto_checkbox.isChecked() or not self.analysis_checkbox.isChecked()):
            return
        proposal = self._v1_pending
        if proposal is None:
            return
        if reservation[:4] != (self._live_run_id, self._live_board_generation,
                               self._live_action_count, proposal.token):
            return
        if proposal.is_guess and not self.allow_guess_checkbox.isChecked():
            self._schedule_v1_step()
            return
        try:
            self._admit_live_proposal(proposal)
            if k_live.is_k_policy(self._live_policy):
                self._k_validation_nonce = uuid4().hex
                self._v1_job.validate_pending(self._v1_snapshot(), self._k_validation_nonce)
                # The viewing interval has elapsed. Waiting here for ADMITTED
                # is purely visual and supplies no input permission.
                self.auto_cursor_overlay.reserve(
                    self._k_validation_nonce, self._v1_cursor, (proposal.x, proposal.y), 0)
                self._v1_status = "현재 K 입력 검증 중"
                self._update_policy_controls()
                return
            admitted = self._v1_job.mark_applying(proposal.token)
            self._v1_pending = None
            if admitted != proposal:
                raise ValueError("승인된 V1 입력과 표시된 추천이 다릅니다.")
            admit_proposal(admitted, self._v1_snapshot())
            if admitted.initial and (not self._live_fresh_reset or self._live_action_count != 0
                                     or self.engine.get_board_snapshot().mines_placed):
                raise ValueError("V1 첫 입력의 새 게임 상태가 달라졌습니다.")
            event_index = self._apply_live_action(
                admitted.x, admitted.y, admitted.move.action,
                auto_observation=admitted.snapshot.observation,
            )
            # Status is the first policy-facing read after the actual input.
            status = self.engine.status
            after = self.engine.get_observation() if status == GameStatus.PLAYING else None
            self._v1_input_seq = admitted.snapshot.input_seq + 1
            totals = self.live_auto_totals
            category = "preparation" if admitted.is_flag_review else "v1"
            totals[category + "_inputs"] += 1
            totals[category + "_modeled_us"] += admitted.modeled_action_us
            totals["modeled_us"] += admitted.modeled_action_us
            record = {
                "game_id": self._live_game_id, "entry_mode": admitted.snapshot.entry_mode,
                "phase": admitted.phase, "input_revision_before": admitted.snapshot.input_revision,
                "input_revision_after": self._live_action_count,
                "run_id": self._live_run_id, "board_generation": self._live_board_generation,
                "policy_id": POLICY_V1, "input_seq": admitted.snapshot.input_seq,
                "token": admitted.token, "action": admitted.action, "x": admitted.x, "y": admitted.y,
                "before": admitted.snapshot.observation,
                "after": None if after is None else tuple(tuple(row) for row in after),
                "status": status.name, "cursor_before": admitted.snapshot.cursor,
                "cursor_after": self._v1_cursor, "modeled_action_us": admitted.modeled_action_us,
                "compute_ns": admitted.compute_ns, "event_index": event_index,
                "review_compute_ns": admitted.review_compute_ns,
                "semantic_input": "UNFLAG" if admitted.is_flag_review else admitted.action,
                "review": None if admitted.review is None else report_to_dict(admitted.review),
                "auto_totals": dict(totals),
                "game_wall_seconds": self.engine.get_elapsed_time(), "ack_sent": False,
            }
            self.live_action_records.append(record)
            if event_index is None:
                raise RuntimeError("실제 입력의 Replay 기록을 확인할 수 없습니다.")
            ack = make_ack(admitted, status.name, observation=after)
            next_snapshot = validate_ack(admitted, ack)
            self._v1_expected_ack = ack
            if next_snapshot is not None:
                if next_snapshot.input_revision != self._live_action_count:
                    raise RuntimeError("실제 입력 revision이 V1 확인과 다릅니다.")
                self._v1_phase = next_snapshot.phase
                self._v1_review_inputs = next_snapshot.review_inputs
            self._v1_job.acknowledge(status.name, observation=after)
            record["ack_sent"] = True
            self._v1_status = "입력 확인 중" if status == GameStatus.PLAYING else "게임 종료 · worker 정리 중"
            self._update_policy_controls()
            self.live_action_applied.emit(dict(record))
        except Exception as exc:
            self._fail_v1(str(exc))

    def _on_k_admitted(self, permit):
        if (not k_live.is_k_policy(self._live_policy) or self._live_closing or self._replay_mode
                or not self._v1_owned or self._k_retired):
            return
        if type(permit) is not k_live.KPermit:
            self._fail_v1("잘못된 K 승인 형식")
            return
        if permit.nonce != self._k_validation_nonce or self._v1_job.state != "admitted":
            # A revoked in-flight response has now drained. A new reservation
            # is allowed; duplicates must never revoke a newer validation.
            if self._v1_job.state == "pending" and self._k_validation_nonce is None:
                self._schedule_v1_step()
            return
        if (self._mouse_buttons or self._live_input_uncertain or self._v1_manual_only
                or self.engine.status != GameStatus.PLAYING
                or not self.simple_auto_checkbox.isChecked() or not self.analysis_checkbox.isChecked()
                or (permit.proposal.is_guess and not self.allow_guess_checkbox.isChecked())):
            self._cancel_simple_auto_step()
            return
        record = None
        try:
            permit.__post_init__()
            proposal = self._admit_live_proposal(permit.proposal)
            if proposal != self._v1_pending:
                raise ValueError("K 승인과 보관 추천이 다릅니다.")
            if not self._v1_supported() or not self._known_live_history():
                raise ValueError("K 입력의 보드 지원·실제 입력 이력이 달라졌습니다.")
            if proposal.initial and not self._k_fresh_start():
                raise ValueError("K 첫 입력의 새 게임 상태가 달라졌습니다.")
            # No event-loop yield/modal/await between final full comparison,
            # token consumption and this one actual engine input.
            owner_record = next((item for item in reversed(self.live_owner_records)
                                 if item['run_id'] == self._live_run_id), None)
            if owner_record is None:
                raise ValueError('K owner record is missing before input.')
            admitted = self._v1_job.mark_applying(proposal.token, permit.nonce)
            if admitted != proposal:
                raise ValueError("K 소비 token이 승인과 다릅니다.")
            self._v1_pending = None
            before_events = len(self._replay_recorder.events)
            counters = self.engine.get_counter_snapshot()
            before_inputs = counters['active_clicks'] + counters['wasted_clicks']
            record = {
                'game_id': self._live_game_id, 'run_id': self._live_run_id,
                'board_generation': self._live_board_generation, 'policy_id': proposal.snapshot.policy_id,
                'definition': proposal.snapshot.definition, 'entry_mode': proposal.snapshot.entry_mode,
                'start_input_revision': proposal.snapshot.start_input_revision,
                'k_start_input_revision': proposal.snapshot.k_start_input_revision,
                'phase': proposal.snapshot.phase, 'preparation_seq': proposal.snapshot.preparation_seq,
                'semantic_input': 'UNFLAG' if proposal.is_preparation else proposal.action,
                'bootstrap': k_live.to_dict(proposal.snapshot.bootstrap) if proposal.snapshot.bootstrap else None,
                'input_seq': proposal.snapshot.input_seq,
                'input_revision_before': proposal.snapshot.input_revision,
                'token': proposal.token, 'permit_nonce': permit.nonce,
                'action': proposal.action, 'x': proposal.x, 'y': proposal.y,
                'category': proposal.category, 'continuation': proposal.continuation,
                'M_before': proposal.snapshot.base_m, 'preinput_M': proposal.preinput_m,
                'base_m_revision': proposal.snapshot.base_m_revision,
                'pending_m_revision': proposal.pending_m_revision,
                'before': proposal.snapshot.observation, 'cursor_before': proposal.snapshot.cursor,
                'profile_sha256': proposal.snapshot.profile_sha256,
                'table_sha256': proposal.snapshot.table_sha256,
                'modeled_action_us': proposal.modeled_action_us, 'compute_ns': proposal.compute_ns,
                'event_index': None, 'actual_input_confirmed': False,
                'ack_sent': False, 'ack_state': 'NOT_SENT', 'incomplete_reason': None,
                'end_reason': None, 'cleanup': None,
            }
            self.live_action_records.append(record)
            owner_record['k_actions'].append(record)
            try:
                event_index = self._apply_live_action(proposal.x, proposal.y, proposal.move.action,
                                                       auto_observation=proposal.snapshot.observation)
            finally:
                # Preserve actual input/event evidence even if archival/render
                # work after engine.step failed. Never retry this token.
                status = self.engine.status
                after = self.engine.get_observation() if status == GameStatus.PLAYING else None
                counts = self.engine.get_counter_snapshot()
                actual = counts['active_clicks'] + counts['wasted_clicks'] > before_inputs
                events = len(self._replay_recorder.events)
                record.update(status=status.name, after=None if after is None else tuple(tuple(r) for r in after),
                              cursor_after=self._v1_cursor, input_revision_after=self._live_action_count,
                              event_index=before_events if events == before_events + 1 else None,
                              actual_input_confirmed=actual)
                if actual:
                    category = 'preparation' if proposal.is_preparation else 'k'
                    self.live_auto_totals[category + '_inputs'] += 1
                    self.live_auto_totals[category + '_modeled_us'] += proposal.modeled_action_us
                    self.live_auto_totals['modeled_us'] += proposal.modeled_action_us
                    owner_record[category + '_input_count'] += 1
                record['auto_totals'] = dict(self.live_auto_totals)
            if not record['actual_input_confirmed'] or event_index is None or event_index != record['event_index']:
                raise RuntimeError("실제 K 입력의 Replay 기록을 확인할 수 없습니다.")
            self._v1_input_seq = proposal.snapshot.input_seq + int(not proposal.is_preparation)
            self._k_preparation_seq = proposal.snapshot.preparation_seq + int(proposal.is_preparation)
            ack = k_live.make_ack(permit, status.name, observation=after)
            self._v1_expected_ack = ack
            self._v1_job.acknowledge(status.name, observation=after)
            record.update(ack_sent=True, ack_state='SENT')
            record['expected_ack'] = k_live.to_dict(ack)
            self._k_ack_receipt = self._seal_k_receipt(ack, record)
            self._v1_status = "K 입력 확인 중" if status == GameStatus.PLAYING else "게임 종료 · worker 정리 중"
            self._update_policy_controls()
            self.live_action_applied.emit(dict(record))
        except Exception as exc:
            if record is not None:
                record['incomplete_reason'] = str(exc)
                self._live_input_uncertain = True
            self._fail_v1(str(exc))

    def _on_k_acknowledged(self, ack):
        retiring = self._k_retiring
        if retiring is not None and ack.run_id == retiring.ack.run_id:
            try:
                action = self._verify_k_receipt(retiring, ack)
                action['ack_state'] = 'ACKED'
                self._k_retiring = replace(retiring, acknowledged=True)
                # No current-board/M/cursor/revision writes and no NEXT here.
                self._v1_job.cancel("수동 인계 · 원 입력 확인 완료")
                self._update_policy_controls()
            except Exception as exc:
                self._fail_v1(str(exc))
            return
        if (not k_live.is_k_policy(self._live_policy) or self._live_closing or self._replay_mode
                or not self._v1_owned or ack.run_id != self._live_run_id):
            return
        try:
            self._verify_k_receipt(self._k_ack_receipt, ack)
            ack.__post_init__()
            expected = k_live.next_snapshot(ack.permit.proposal, ack)
            if (ack != self._v1_expected_ack or expected is None
                    or self.engine.status != GameStatus.PLAYING):
                raise ValueError("K ACK가 실제 입력과 다릅니다.")
            current = k_live.make_snapshot(
                run_id=self._live_run_id, board_generation=self._live_board_generation,
                input_seq=self._v1_input_seq, input_revision=self._live_action_count,
                width=self.engine.width, height=self.engine.height, num_mines=self.engine.num_mines,
                observation=self.engine.get_observation(), cursor=self._v1_cursor,
                base_m_revision=expected.base_m_revision, base_m=expected.base_m,
                entry_mode=self._v1_entry_mode, start_input_revision=self._k_start_input_revision,
                phase=expected.phase, preparation_seq=self._k_preparation_seq,
                k_start_input_revision=self._k_normal_start, bootstrap=self._k_bootstrap,
                game_id=self._live_game_id, policy_id=self._live_policy,
                definition=k_live.definition_for_entry(self._v1_entry_mode, self._live_policy))
            if current != expected or not self._known_live_history():
                raise ValueError("K ACK 뒤 현재 공개 상태/binding이 다릅니다.")
            self._k_base_m, self._k_m_revision = expected.base_m, expected.base_m_revision
            self._k_phase = expected.phase
            self._record_k_policy_start()
            self._v1_expected_ack = None
            self._k_ack_receipt = None
            for record in reversed(self.live_action_records):
                if record.get('token') == ack.token and record.get('run_id') == ack.run_id:
                    record['ack_state'] = 'ACKED'
                    break
            for owner in reversed(self.live_owner_records):
                if owner['run_id'] == self._live_run_id:
                    owner['k_ack_count'] += 1
                    break
            self._v1_status = "일시정지 · K 입력 확인 완료"
            if (self.simple_auto_checkbox.isChecked() and self.analysis_checkbox.isChecked()
                    and not self._mouse_buttons and not self._k_retired):
                self._v1_job.request(current)
                self._v1_status = "K 계산 중"
            self._update_policy_controls()
        except Exception as exc:
            self._live_input_uncertain = True
            self._fail_v1(str(exc))

    def _on_v1_acknowledged(self, ack):
        if type(ack) is k_live.KAck:
            self._on_k_acknowledged(ack)
            return
        if (self._live_closing or self._replay_mode or not self._v1_owned
                or ack.run_id != self._live_run_id):
            return
        try:
            current = self._v1_snapshot()
            if (ack != self._v1_expected_ack
                    or ack.board_generation != current.board_generation or ack.policy_id != current.policy_id
                    or ack.input_seq + 1 != current.input_seq or ack.status != "PLAYING"
                    or ack.input_revision != current.input_revision or ack.entry_mode != current.entry_mode
                    or ack.observation != current.observation or current.cursor != (ack.x, ack.y)):
                raise ValueError("V1 입력 확인 뒤 공개 상태가 달라졌습니다.")
            self._v1_expected_ack = None
            self._v1_status = "일시정지" if not self.simple_auto_checkbox.isChecked() else "계산 중"
            if self.simple_auto_checkbox.isChecked() and self.analysis_checkbox.isChecked():
                self._v1_job.request(current)
            self._update_policy_controls()
        except Exception as exc:
            self._fail_v1(str(exc))

    def _on_v1_finished(self, record):
        receipt = self._k_retiring or self._k_ack_receipt
        if receipt is not None and receipt.ack.run_id == record.get('run_id'):
            clean = (record.get('cleanup_complete') is True and record.get('reaped') is True
                     and record.get('tree_active_count') == 0 and not record.get('error'))
            confirmed = receipt.acknowledged
            if (not confirmed and clean and record.get('status') == 'SUCCEEDED'
                    and receipt.ack.status in ('WON', 'LOST')
                    and record.get('last_k_ack') == k_live.to_dict(receipt.ack)):
                try:
                    self._verify_k_receipt(receipt, receipt.ack)
                    confirmed = True
                except Exception as exc:
                    self._record_live_failure(str(exc), stage='terminal ACK')
            if not (clean and confirmed and record.get('status') in ('CANCELLED', 'SUCCEEDED')):
                self._record_live_failure(
                    record.get('error') or ("worker 정리 실패" if not clean else "원 입력 ACK 미확인"),
                    stage='cleanup' if confirmed else 'ACK')
                self._set_auto_off(clear_guess=True)
            else:
                self._v1_expected_ack = None
            self._k_retiring = self._k_ack_receipt = None
        retained_actions = [action for owner in self.live_owner_records
                            for action in owner.get('k_actions', [])]
        for action in retained_actions:
            if action.get("run_id") == record.get("run_id") and k_live.is_k_policy(action.get("policy_id")):
                action['cleanup'] = dict(record)
                action['end_reason'] = record.get('error') or record.get('intent_reason') or record.get('status')
                if (record.get('status') == 'SUCCEEDED' and record.get('cleanup_complete') is True
                        and record.get('last_k_ack') == action.get('expected_ack')
                        and action.get('expected_ack') is not None
                        and action.get('ack_sent') and action.get('status') in ('WON', 'LOST')):
                    action['ack_state'] = 'ACKED'
                if action.get('actual_input_confirmed') and action.get('ack_state') != 'ACKED':
                    action['ack_state'] = 'INCOMPLETE'
                    action['incomplete_reason'] = (action.get('incomplete_reason')
                                                   or action['end_reason'] or 'ACK not confirmed')
        for owner in reversed(self.live_owner_records):
            if owner["run_id"] == record.get("run_id"):
                owner["cleanup"] = dict(record)
                if owner.get('first_failure') is not None:
                    owner['first_failure']['cleanup_result'] = dict(record)
                if k_live.is_k_policy(owner['policy_id']):
                    owner['k_ack_count'] = sum(a.get('ack_state') == 'ACKED' for a in owner['k_actions'])
                    owner['preparation_ack_count'] = sum(a.get('ack_state') == 'ACKED'
                        and a.get('semantic_input') == 'UNFLAG' for a in owner['k_actions'])
                    owner['k_policy_ack_count'] = owner['k_ack_count'] - owner['preparation_ack_count']
                if owner["end_reason"] is None:
                    owner.update(end_reason=record.get("error") or record.get("status"),
                                 end_revision=self._live_action_count,
                                 end_event_index=len(self._replay_recorder.events),
                                 end_cursor=self._v1_cursor)
                break
        if self._live_closing:
            return
        if record.get("run_id") != self._live_run_id:
            self._update_policy_controls()
            return
        # Selection can change while this owner is being retired. Its unexpected
        # failure must not disappear merely because Simple is now selected.
        if not self._v1_owned and (record.get("error") or record.get("cleanup_complete") is not True
                                  or record.get("status") not in ("CANCELLED", "CLOSED", "SUCCEEDED")):
            self._v1_manual_only = True
            self._live_input_uncertain = True
            self._record_live_failure(record.get('error') or record.get('status'), stage='cleanup')
            if k_live.is_k_policy(record.get("policy_id")):
                self._k_retired = True
            cleanup = "정리 완료" if record.get("cleanup_complete") is True else "정리 실패"
            self._v1_status = f"수동 · 이전 Auto worker 오류 · {cleanup}"
            self._stop_simple_auto()
            self._clear_live_analysis(f"이전 Auto 오류 - {record.get('error') or record.get('status')}")
            self._update_policy_controls()
            return
        if self._live_policy not in (POLICY_V1, POLICY_K, POLICY_K_LC0, POLICY_K_LC1):
            self._update_policy_controls()
            return
        if (record.get("status") == "SUCCEEDED" and record.get("cleanup_complete") is True
                and self.engine.status != GameStatus.PLAYING):
            self._v1_owned = False
            self._v1_pending = None
            self._v1_expected_ack = None
            self._set_auto_off(clear_guess=True)
            self._v1_status = f"{self.engine.status.name} · 정리 완료"
            self._update_policy_controls()
        elif self._v1_owned:
            error = record.get("error") or record.get("status", "worker 종료")
            self._fail_v1(error)
            if self.engine.status in (GameStatus.WON, GameStatus.LOST):
                reason = "worker 종료 지연" if error.startswith("FINISH_EXIT_TIMEOUT:") else "worker 실패"
                cleanup = "정리 완료" if record.get("cleanup_complete") is True else "정리 실패"
                self._v1_status = f"{self.engine.status.name} · {reason} · {cleanup}"
                self._update_policy_controls()
        else:
            if self._v1_job.state == "idle" and not self._v1_manual_only:
                self._v1_status = (f"수동 · 정리 완료 · 현재 판을 {k_live.policy_label(self._live_policy)}로 인수 가능" if k_live.is_k_policy(self._live_policy)
                                   else "수동 · 정리 완료 · Auto ON으로 다시 인수")
            self._update_policy_controls()

    def _invalidate_analysis_state(self):
        self._cancel_simple_auto_step()
        self._analysis_result = None
        self._replay_analysis_result = None
        self._analysis_observation = None
        self._analysis_first_click = False

    def _clear_live_analysis(self, status="분석 대기", *, keep_certainty=False):
        self._invalidate_analysis_state()
        if not keep_certainty:
            self._certainty_frame = None
        self._replay_reference_error = status if status.startswith("분석 불가") else None
        self.analysis_status_label.setText(status)
        self._render_live_analysis()

    def _display_context(self, *, previous_observation=None):
        """Read-only display epoch; never consulted by input/ACK validation."""
        if (self._replay_mode or self._live_closing or self._live_input_uncertain
                or self._live_first_failure is not None or self._v1_manual_only
                or not self.analysis_checkbox.isChecked()
                or self.engine.status != GameStatus.PLAYING or not self._known_live_history()):
            return None
        worker = self._live_policy != POLICY_SIMPLE
        if worker and (not self._v1_owned or self._v1_job.active_run_id != self._live_run_id):
            return None
        records = self.live_input_records
        events = self._replay_recorder.events
        revision = self._live_action_count
        observation = self.engine.get_observation()
        if previous_observation is not None:
            if not records or not records[-1]['automatic']:
                return None
            records, events = records[:-1], events[:-1]
            revision -= 1
            observation = previous_observation
        history = (tuple(tuple(sorted(row.items())) for row in records), tuple(events))
        digest = lambda value: sha256(repr(value).encode('utf-8')).hexdigest()
        return DisplayContext(self._live_game_id, self._live_policy, self._live_run_id,
                              self._live_board_generation, id(self._v1_job) if worker else 0,
                              revision, digest(history),
                              digest(tuple(tuple(row) for row in observation)))

    def _remember_live_certainty(self, *, preparing=False):
        context = None if preparing else self._display_context()
        self._certainty_frame = (CertaintyFrame.capture(
            context, self._analysis_result.overlays, self.engine.get_observation())
            if context is not None else None)

    def _render_live_analysis(self):
        result = self._analysis_result
        target = None
        overlays = result.overlays if result is not None else {}
        if self._replay_mode and self._replay_player is not None:
            player = self._replay_player
            text, target = recorded_input(player.replay_data.events, player.current_index,
                                          player.get_observation(), player.engine.status)
            overlays = {}
            if self.analysis_checkbox.isChecked():
                text += "\n" + reference_text(result, player.engine.status, self._replay_reference_error)
                overlays = reference_overlays(result)
            self.analysis_status_label.setText(text)
        elif result is None and self._certainty_frame is not None:
            if (type(self._certainty_frame) is CertaintyFrame
                    and self._certainty_frame.context == self._display_context()):
                overlays = self._certainty_frame.overlays()
            else:
                self._certainty_frame = None
        for coordinate, button in self._buttons.items():
            button.set_analysis_overlay(overlays.get(coordinate), self.probability_checkbox.isChecked(),
                                        recorded_target=coordinate == target)

    def on_analysis_toggled(self, enabled: bool):
        if enabled and self._mouse_buttons and not self._replay_mode:
            blocked = self.analysis_checkbox.blockSignals(True)
            self.analysis_checkbox.setChecked(False)
            self.analysis_checkbox.blockSignals(blocked)
            return
        if enabled and k_live.is_k_policy(self._live_policy) and not self._replay_mode:
            # Display toggles never start/advance K reasoning. Explicit Analyze
            # or Auto ON owns that request; an existing pending is only rendered.
            if self._v1_pending is not None:
                self._show_v1_pending()
            return
        if enabled:
            self.on_analyze_current()
        else:
            self._v1_display_requested = False
            self._stop_simple_auto()
            self._clear_live_analysis()

    def on_analyze_current(self):
        # Explicit button/keyboard/signal activation is distinct from the
        # internal Simple refresh after an actual RIGHT press or chord input.
        if (not self._replay_mode
                and (self._mouse_buttons or self._live_closing or self._live_input_uncertain)):
            return
        if self._replay_mode:
            self._analyze_current_replay()
            return
        if self._live_policy in (POLICY_V1, POLICY_K, POLICY_K_LC0, POLICY_K_LC1):
            self._v1_display_requested = True
            self._analyze_v1_current()
            return
        self._analyze_simple_current()

    def _analyze_simple_current(self):
        if self._live_input_uncertain or self._live_closing:
            self._set_auto_off(clear_guess=True)
            self._clear_live_analysis(self._live_failure_text())
            return
        if self._v1_job.state not in ("idle", "closed"):
            self._clear_live_analysis("이전 Auto 정리 후 분석할 수 있습니다.")
            return
        if self.engine.status != GameStatus.PLAYING:
            self._stop_simple_auto()
            self._clear_live_analysis("게임 종료")
            return
        self._invalidate_analysis_state()
        try:
            observation = self.engine.get_observation()
            binding = self._simple_binding()
            if self._simple_expected_binding is not None and binding != self._simple_expected_binding:
                self._reset_simple_preparation()
            if self._simple_review_dirty:
                self._simple_preparation = (prepare_flags(observation, self.engine.num_mines)
                    if any(v == CellState.FLAGGED for row in observation for v in row) else None)
                self._simple_preparation_start = self._live_action_count
                self._simple_preparation_seq = 0
                self._simple_review_dirty = False
            self._simple_expected_binding = binding
            preparation = self._simple_preparation
            # FLAG then unflag can hide every cell on an already fixed board.
            # Only the public placement boolean participates in this UI policy.
            first_click = (is_all_hidden(observation)
                           and not self.engine.get_board_snapshot().mines_placed)
            if preparation is not None and self._simple_preparation_seq < len(preparation.removable):
                first_click = False
                target = preparation.target(self._simple_preparation_seq,
                                            tuple(tuple(row) for row in observation))
                result = present_flag_preparation("Simple", target, len(preparation.retained),
                    len(preparation.removable), "공개 단서·총수의 직접 추론 범위입니다.")
            elif first_click:
                result = first_click_presentation()
            else:
                decision = analyze_position(observation, self.engine.num_mines)
                result = present_decision(observation, decision)
        except InconsistentObservationError:
            self._set_auto_off(clear_guess=True)
            self._clear_live_analysis("분석 불가 - 공개 상태가 모순됩니다.")
            return
        except Exception as error:
            # Solver validation/failure must not escape a Qt slot or trigger moves.
            self._set_auto_off(clear_guess=True)
            self._clear_live_analysis(f"분석 불가 - {error}")
            return
        self._analysis_result = result
        self._analysis_observation = tuple(tuple(row) for row in observation)
        self._analysis_first_click = first_click
        self._simple_analysis_binding = binding
        self.analysis_status_label.setText(result.status_text)
        self._remember_live_certainty(preparing=(preparation is not None
            and self._simple_preparation_seq < len(preparation.removable)))
        self._render_live_analysis()
        self._schedule_simple_auto_step()

    def _analyze_current_replay(self):
        """Read only public replay state; never schedule/execute a solver action."""
        self._stop_simple_auto()
        self._clear_live_analysis()
        if self._replay_player is None or not self.analysis_checkbox.isChecked():
            return
        try:
            player = self._replay_player
            result = analyze_replay_step(
                player.get_observation(), player.engine.num_mines,
                current_index=player.current_index,
                events=player.replay_data.events, status=player.engine.status,
            )
            self._replay_analysis_result = result
            self._analysis_result = result.presentation
            self._render_live_analysis()
        except InconsistentObservationError:
            self._clear_live_analysis("분석 불가 - 공개 상태가 모순됩니다.")
        except Exception:
            # Keep playback/navigation alive, including validation/runtime errors.
            self._clear_live_analysis("분석 불가 - 현재 상태를 분석할 수 없습니다.")

    def _refresh_live_board(self, info=None, *, auto_observation=None):
        """After each physical action: invalidate, render, analyze fresh, overlay."""
        frame = self._certainty_frame
        self._certainty_frame = (frame.advance(
            self._display_context(previous_observation=auto_observation),
            self._display_context(), self.engine.get_observation())
            if type(frame) is CertaintyFrame and auto_observation is not None else None)
        self._clear_live_analysis("다음 수 계산 중" if self._certainty_frame else "분석 대기",
                                  keep_certainty=True)
        self.render_board()
        if info is not None:
            self._apply_stats_from_info(info)
            self._check_end_state()
        if self._replay_mode or self.engine.status != GameStatus.PLAYING:
            self._set_auto_off(clear_guess=True)
            return
        if self._live_policy in (POLICY_V1, POLICY_K, POLICY_K_LC0, POLICY_K_LC1):
            self._update_policy_controls()
            return
        if auto_observation is not None:
            if self._simple_applying_preparation:
                prep = self._simple_preparation
                expected = prep.observation_after(self._simple_preparation_seq + 1)
                if tuple(tuple(row) for row in self.engine.get_observation()) != expected:
                    self._live_input_uncertain = True
                    raise ValueError("깃발 정리가 정확한 한 칸 해제와 다릅니다.")
                self._simple_preparation_seq += 1
            hidden_before = sum(value == CellState.HIDDEN
                                for row in auto_observation for value in row)
            hidden_after = sum(value == CellState.HIDDEN
                               for row in self.engine.get_observation() for value in row)
            if not self._simple_applying_preparation and hidden_after >= hidden_before:
                self._fail_simple_auto("실행 후 보드가 진행되지 않았습니다.")
                return
            # Our own FLAG/UNFLAG never starts another preparation epoch.
            self._simple_expected_binding = self._simple_binding()
        if self.analysis_checkbox.isChecked():
            self._analyze_simple_current()

    def _reset_simple_preparation(self):
        self._simple_preparation = None
        self._simple_preparation_seq = 0
        self._simple_review_dirty = True
        self._simple_expected_binding = None
        self._simple_analysis_binding = None

    def _simple_binding(self):
        counters = self.engine.get_counter_snapshot()
        return (self._live_game_id, self._live_board_generation, self._live_action_count,
                self._v1_cursor, self.engine.width, self.engine.height, self.engine.num_mines,
                tuple(tuple(row) for row in self.engine.get_observation()),
                counters['active_clicks'], counters['wasted_clicks'],
                tuple(tuple(sorted(row.items())) for row in self.live_input_records),
                tuple(self._replay_recorder.events))

    def _simple_preparation_move(self, observation):
        prep = self._simple_preparation
        if prep is None or self._simple_preparation_seq == len(prep.removable):
            return None
        if self._live_action_count != self._simple_preparation_start + self._simple_preparation_seq:
            raise ValueError("깃발 정리 입력 순서가 달라졌습니다.")
        target = prep.target(self._simple_preparation_seq, tuple(tuple(row) for row in observation))
        move = self._analysis_result.move
        if (move.action != Action.FLAG or (move.x, move.y) != target
                or observation[move.y][move.x] != CellState.FLAGGED):
            raise ValueError("깃발 정리 대상이 현재 추천과 다릅니다.")
        return move

    def _apply_simple_preparation(self, move, observation):
        before_revision, before_events = self._live_action_count, len(self._replay_recorder.events)
        counters = self.engine.get_counter_snapshot()
        before_inputs = counters['active_clicks'] + counters['wasted_clicks']
        start = self._v1_cursor
        dx, dy = abs(start[0] - move.x), abs(start[1] - move.y)
        if self._simple_timing_table is None:
            self._simple_timing_table = load_timing_table()
        cost = (action_cost(self._simple_timing_table, (0, 0), (dx, dy))
                if dx < 30 and dy < 16 else None)
        record = dict(game_id=self._live_game_id, policy_id=POLICY_SIMPLE,
                      phase='SIMPLE_FLAG_PREPARATION', semantic_input='UNFLAG',
                      action='FLAG', x=move.x, y=move.y,
                      input_revision_before=before_revision, cursor_before=start,
                      preparation_seq=self._simple_preparation_seq,
                      before=tuple(tuple(row) for row in observation),
                      modeled_action_us=cost, profile_sha256=PROFILE_SHA256, table_sha256=TABLE_SHA256,
                      modeled_cost_status='EXACT' if cost is not None else 'OUTSIDE_FROZEN_TABLE',
                      actual_input_confirmed=False, event_index=None)
        self.live_action_records.append(record)
        self._simple_applying_preparation = True
        try:
            event = self._apply_live_action(move.x, move.y, Action.FLAG, auto_observation=observation)
            if (event != before_events or len(self._replay_recorder.events) != before_events + 1
                    or self._live_action_count != before_revision + 1 or self._live_input_uncertain):
                raise ValueError("깃발 정리의 실제 입력/Replay 기록을 확인할 수 없습니다.")
            record['actual_input_confirmed'] = True
        except Exception as exc:
            record['incomplete_reason'] = str(exc)
            self._record_live_failure(str(exc), stage='Simple preparation input')
            raise
        finally:
            self._simple_applying_preparation = False
            counters = self.engine.get_counter_snapshot()
            actual = counters['active_clicks'] + counters['wasted_clicks'] == before_inputs + 1
            record.update(input_revision_after=self._live_action_count, cursor_after=self._v1_cursor,
                          event_index=before_events if len(self._replay_recorder.events) == before_events + 1 else None,
                          after=tuple(tuple(row) for row in self.engine.get_observation()))
            record['actual_input_confirmed'] = actual
            if actual:
                self.live_auto_totals['preparation_inputs'] += 1
                if cost is not None:
                    self.live_auto_totals['preparation_modeled_us'] += cost
                    self.live_auto_totals['modeled_us'] += cost
                else:
                    self.live_auto_totals['preparation_unmodeled_inputs'] += 1

    def _cancel_simple_auto_step(self):
        self._simple_auto_timer.stop()
        self._simple_auto_pending = False
        self._v1_timer_nonce += 1
        self._v1_timer_reservation = None
        self._k_validation_nonce = None
        if k_live.is_k_policy(self._live_policy):
            self._v1_job.invalidate_admission()
        if hasattr(self, "auto_cursor_overlay"):
            self.auto_cursor_overlay.cancel()

    def _on_auto_cursor_display_toggled(self, enabled):
        # Display only: do not reschedule input or invalidate a K permit/nonce.
        self.auto_cursor_overlay.set_display_enabled(enabled)

    def _connect_auto_timeout(self, slot):
        # Disconnecting alone does not cancel already queued Qt deliveries;
        # each V1 slot also retains and validates its original reservation.
        self._simple_auto_timer.timeout.disconnect(self._simple_auto_timeout_slot)
        self._simple_auto_timeout_slot = slot
        self._simple_auto_timer.timeout.connect(slot)

    def _set_auto_off(self, *, clear_guess):
        self._cancel_simple_auto_step()
        controls = ((self.simple_auto_checkbox, self.allow_guess_checkbox) if clear_guess
                    else (self.simple_auto_checkbox,))
        for checkbox in controls:
            blocked = checkbox.blockSignals(True)
            checkbox.setChecked(False)
            checkbox.blockSignals(blocked)
        self.allow_guess_checkbox.setEnabled(False)

    def _stop_simple_auto(self, *, pause=False):
        self._set_auto_off(clear_guess=not pause)
        if self._v1_owned and self.engine.status == GameStatus.PLAYING:
            self._v1_status = "일시정지 · 추천/계산 보관"
            self._update_policy_controls()

    def _fail_simple_auto(self, message):
        if self._live_policy in (POLICY_V1, POLICY_K, POLICY_K_LC0, POLICY_K_LC1):
            self._fail_v1(message)
            return
        self._set_auto_off(clear_guess=True)
        if self._live_input_uncertain:
            self._record_live_failure(message, stage='Simple input')
        self._clear_live_analysis(f"자동 진행 중지 - {message}")

    def _on_simple_auto_interval_edited(self, text: str):
        spin = self.simple_auto_interval_spin
        # textEdited precedes Qt's value update. Refresh valid zero input through
        # setValue so specialValueText appears even when zero is entered again.
        if spin.hasAcceptableInput() and spin.valueFromText(text) == 0:
            spin.setValue(0)

    def on_simple_auto_interval_changed(self, interval: int):
        # Qt restarts an active timer when its interval changes. Keep the same
        # pending step and analysis; even 0 waits for event-loop dispatch.
        self._simple_auto_timer.setInterval(interval)
        if self._live_policy in (POLICY_V1, POLICY_K, POLICY_K_LC0, POLICY_K_LC1) and not self._replay_mode:
            self._schedule_v1_step()

    def on_simple_auto_toggled(self, enabled):
        if not enabled:
            self._stop_simple_auto(pause=True)
            return
        if enabled and self._mouse_buttons and not self._replay_mode:
            self._stop_simple_auto()
            return
        if self._live_policy in (POLICY_V1, POLICY_K, POLICY_K_LC0, POLICY_K_LC1) and not self._replay_mode:
            if (not enabled or self._live_closing or self._v1_manual_only
                    or self._live_input_uncertain or self._mouse_buttons
                    or self.engine.status != GameStatus.PLAYING):
                self._stop_simple_auto()
                return
            self.allow_guess_checkbox.setEnabled(True)
            if not self.analysis_checkbox.isChecked():
                self.analysis_checkbox.setChecked(True)
                if k_live.is_k_policy(self._live_policy):
                    self._analyze_v1_current()
            else:
                self._analyze_v1_current()
            return
        if (not enabled or self._replay_mode
                or self._live_input_uncertain
                or self._v1_job.state not in ("idle", "closed")
                or self.engine.status != GameStatus.PLAYING):
            self._stop_simple_auto()
            return
        self.allow_guess_checkbox.setEnabled(True)
        if not self.analysis_checkbox.isChecked():
            # The toggled signal performs exactly one fresh analysis.
            self.analysis_checkbox.setChecked(True)
        else:
            self.on_analyze_current()

    def on_allow_guess_toggled(self, _enabled):
        if self._live_policy in (POLICY_V1, POLICY_K, POLICY_K_LC0, POLICY_K_LC1) and not self._replay_mode:
            self._schedule_v1_step()
            return
        if not self.simple_auto_checkbox.isChecked() or self._replay_mode:
            self._stop_simple_auto()
            return
        # Reuse the current decision, including its original guess tie-break.
        self._schedule_simple_auto_step()

    def _simple_auto_move(self, observation):
        """Validate against public state, then apply policy; None means guess wait."""
        if self._simple_analysis_binding != self._simple_binding():
            raise ValueError("추천의 게임/입력 이력이 현재 보드와 일치하지 않습니다.")
        if tuple(tuple(row) for row in observation) != self._analysis_observation:
            raise ValueError("추천이 현재 보드와 일치하지 않습니다.")
        result = self._analysis_result
        if result is None or result.move is None:
            raise ValueError("진행 중인 보드에 추천 수가 없습니다.")
        preparation = self._simple_preparation_move(observation)
        if preparation is not None:
            return preparation
        if self._analysis_first_click:
            # No hidden layout fields enter move selection, even at timeout.
            if (not is_all_hidden(observation)
                    or self.engine.get_board_snapshot().mines_placed):
                raise ValueError("첫 클릭 추천이 더 이상 유효하지 않습니다.")
        elif result.decision is None or result.decision.kind not in (
            DecisionKind.LOCAL_DETERMINISTIC, DecisionKind.GLOBAL_CERTAINTY,
            DecisionKind.PROBABILITY_GUESS,
        ):
            raise ValueError("지원하지 않는 추천 종류입니다.")
        move = result.move
        if (
            not isinstance(move.action, Action)
            or move.action not in (Action.OPEN, Action.FLAG)
            or any(isinstance(value, bool) or not isinstance(value, int)
                   for value in (move.x, move.y))
            or not (0 <= move.x < self.engine.width and 0 <= move.y < self.engine.height)
            or observation[move.y][move.x] != CellState.HIDDEN
        ):
            raise ValueError("추천은 범위 내 닫힌 칸의 OPEN 또는 FLAG여야 합니다.")
        if (not self._analysis_first_click
                and result.decision.kind == DecisionKind.PROBABILITY_GUESS
                and not self.allow_guess_checkbox.isChecked()):
            return None
        return move

    def _simple_auto_can_run(self):
        if self._mouse_buttons:
            return False
        if (self._replay_mode or self._live_closing or self._live_input_uncertain
                or self._v1_job.state not in ('idle', 'closed') or not self.analysis_checkbox.isChecked()
                or self.engine.status != GameStatus.PLAYING):
            self._stop_simple_auto()
            return False
        return self.simple_auto_checkbox.isChecked()

    def _schedule_simple_auto_step(self):
        if self._live_policy in (POLICY_V1, POLICY_K, POLICY_K_LC0, POLICY_K_LC1) and not self._replay_mode:
            self._schedule_v1_step()
            return
        self._cancel_simple_auto_step()
        if not self._simple_auto_can_run():
            return
        try:
            move = self._simple_auto_move(self.engine.get_observation())
        except Exception as error:
            self._fail_simple_auto(str(error))
            return
        status = self._analysis_result.status_text
        if move is None:
            self.analysis_status_label.setText(status + " | 추측 대기 (추측 허용 꺼짐)")
            return
        self.analysis_status_label.setText(status)
        nonce = self._v1_timer_nonce
        self._connect_auto_timeout(lambda nonce=nonce: self._on_simple_auto_timeout(nonce))
        self._simple_auto_pending = True
        self._simple_auto_timer.start()

    def _on_simple_auto_timeout(self, nonce=None):
        if nonce is not None and nonce != self._v1_timer_nonce:
            return
        if self._live_policy in (POLICY_V1, POLICY_K, POLICY_K_LC0, POLICY_K_LC1) and not self._replay_mode:
            # A generic Simple timeout may have been queued before selection.
            # Only the captured V1 reservation is authorized to execute V1.
            return
        # Also makes canceled/duplicate timeout delivery harmless in tests or Qt.
        pending = self._simple_auto_pending
        self._cancel_simple_auto_step()
        if not pending or not self._simple_auto_can_run():
            return
        try:
            observation = self.engine.get_observation()
            move = self._simple_auto_move(observation)
            if move is not None:
                if self._simple_preparation_move(observation) is not None:
                    self._apply_simple_preparation(move, observation)
                else:
                    self._apply_live_action(move.x, move.y, move.action,
                                            auto_observation=observation)
        except Exception as error:
            self._fail_simple_auto(str(error))

    # ------------------------------------------------------------------
    # 렌더링 (엔진 -> UI)
    # ------------------------------------------------------------------
    def render_board(self):
        """engine.get_observation() 결과만으로 전체 보드를 다시 그린다."""
        engine = self._engine_for_current_mode()
        if engine.status != GameStatus.PLAYING:
            self._stop_simple_auto()
            self._clear_live_analysis("게임 종료")
        obs = engine.get_observation()
        font_size = self._current_font_size()
        border = border_width_for(self._cell_size)

        for y in range(engine.height):
            for x in range(engine.width):
                self._render_cell(self._buttons[(x, y)], obs[y][x], font_size, border)
                if (self.reduction_checkbox.isChecked()
                        and 0 <= obs[y][x] <= 8):
                    # Never feed a reduced number into state-code rendering: N-F
                    # can be negative when the player has placed incorrect flags.
                    reduced = reduced_number(obs, x, y)
                    self._buttons[(x, y)].setText("" if reduced == 0 else str(reduced))

        remaining = engine.num_mines - engine.count_flags()
        self.mine_label.setText(f"💣 {remaining:03d}")
        self._update_mouse_preview()
        self._update_mouse_trace_controls()

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
            "QPushButton:pressed {"
            " background-color: #c0c0c0; border: 1px solid #a0a0a0;"
            "}"
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
        if status in (GameStatus.WON, GameStatus.LOST):
            self._update_same_board_comparison_action()
